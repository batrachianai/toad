"""Outreach panel card widgets.

Four small, theme-agnostic ``Static`` subclasses used by the right-pane
Outreach section. Each accepts plain Python types via ``__init__`` or
``set_data``, recomputes a ``rich.text.Text`` renderable, and refreshes.
No data fetching, no state beyond what the caller supplies.

The Canon palette is surfaced through semantic style names (``success``,
``warning``, ``muted``, ``accent``); widgets translate those names into
Rich style strings via :data:`CANON_STYLES`. Callers that want a different
palette can pass raw Rich style strings directly.
"""

from __future__ import annotations

from typing import Final

from rich.text import Text
from textual.widgets import Static

__all__ = ["CANON_STYLES", "AccountDot", "Histogram", "RankedBar", "StatLine"]

CANON_STYLES: Final[dict[str, str]] = {
    "success": "bold green",
    "warning": "bold yellow",
    "danger": "bold red",
    "muted": "dim",
    "accent": "bold cyan",
    "primary": "bold white",
}

_HISTOGRAM_GLYPHS: Final[str] = " ▁▂▃▄▅▆▇█"
_BAR_FILL: Final[str] = "█"
_BAR_EMPTY: Final[str] = "░"
_DOT_ACTIVE: Final[str] = "●"
_DOT_IDLE: Final[str] = "○"


def _style_for(name: str) -> str:
    return CANON_STYLES.get(name, name)


def _format_int(value: int) -> str:
    return f"{value:,}"


class _CardBase(Static):
    """Shared behaviour: re-render via ``_render()`` and expose ``rendered``.

    Subclasses implement ``_render()`` returning a ``rich.text.Text`` and
    call ``self._refresh_content()`` whenever data changes.
    """

    DEFAULT_CSS = """
    _CardBase {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__("", **kwargs)  # type: ignore[arg-type]
        self._rendered: Text = Text()

    @property
    def rendered(self) -> Text:
        """Current rendered content as a rich ``Text`` — used by tests."""
        return self._rendered

    def _build(self) -> Text:  # pragma: no cover - abstract
        raise NotImplementedError

    def _refresh_content(self) -> None:
        self._rendered = self._build()
        # ``update`` requires a mounted app; if not mounted yet, defer.
        if self.is_mounted:
            self.update(self._rendered)

    def render(self) -> Text:
        return self._rendered


class StatLine(_CardBase):
    """Label, total, and a stacked horizontal bar.

    Used by the Prospects card. Segments are ``(label, value, style_token)``;
    values are clamped to ``total`` and render in declared order. Empty
    segments render an all-muted bar.
    """

    def __init__(
        self,
        label: str,
        total: int = 0,
        segments: tuple[tuple[str, int, str], ...] = (),
        bar_width: int = 40,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._total = total
        self._segments = segments
        self._bar_width = bar_width
        self._rendered = self._build()

    def set_data(
        self,
        total: int,
        segments: tuple[tuple[str, int, str], ...],
    ) -> None:
        self._total = total
        self._segments = segments
        self._refresh_content()

    def _build(self) -> Text:
        text = Text()
        text.append(self._label, style=_style_for("primary"))
        text.append("  ")
        text.append(_format_int(self._total), style=_style_for("accent"))
        text.append("\n")

        total = max(self._total, 0)
        bar_width = max(self._bar_width, 1)
        if total <= 0 or not self._segments:
            text.append(_BAR_EMPTY * bar_width, style=_style_for("muted"))
            return text

        remaining = bar_width
        for _, value, style_token in self._segments:
            if remaining <= 0:
                break
            proportion = max(0, min(value, total)) / total
            cells = int(round(proportion * bar_width))
            cells = min(cells, remaining)
            if cells > 0:
                text.append(_BAR_FILL * cells, style=_style_for(style_token))
                remaining -= cells
        if remaining > 0:
            text.append(_BAR_EMPTY * remaining, style=_style_for("muted"))

        text.append("\n")
        for i, (seg_label, value, style_token) in enumerate(self._segments):
            if i > 0:
                text.append(" · ", style=_style_for("muted"))
            text.append(f"{_format_int(value)} {seg_label}", style=_style_for(style_token))
        return text


class Histogram(_CardBase):
    """Single-row 24-slot histogram (hour-of-day sends).

    Buckets shorter or longer than 24 are padded/truncated silently so the
    row is always ``SLOTS`` cells wide.
    """

    SLOTS: Final[int] = 24

    def __init__(
        self,
        label: str,
        buckets: tuple[int, ...] = (0,) * 24,
        total: int = 0,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._buckets = self._normalize(buckets)
        self._total = total
        self._rendered = self._build()

    def set_data(self, buckets: tuple[int, ...], total: int) -> None:
        self._buckets = self._normalize(buckets)
        self._total = total
        self._refresh_content()

    @classmethod
    def _normalize(cls, buckets: tuple[int, ...]) -> tuple[int, ...]:
        if len(buckets) == cls.SLOTS:
            return buckets
        if len(buckets) > cls.SLOTS:
            return buckets[: cls.SLOTS]
        return buckets + (0,) * (cls.SLOTS - len(buckets))

    def _build(self) -> Text:
        text = Text()
        text.append(self._label, style=_style_for("primary"))
        text.append("  ")
        text.append(_format_int(self._total), style=_style_for("accent"))
        text.append("\n")

        peak = max(self._buckets) if self._buckets else 0
        if peak <= 0:
            text.append(" " * self.SLOTS, style=_style_for("muted"))
        else:
            last_idx = len(_HISTOGRAM_GLYPHS) - 1
            for value in self._buckets:
                if value <= 0:
                    text.append(" ", style=_style_for("muted"))
                    continue
                idx = 1 + int(round((value / peak) * (last_idx - 1)))
                idx = min(max(idx, 1), last_idx)
                text.append(_HISTOGRAM_GLYPHS[idx], style=_style_for("success"))
        text.append("\n")
        axis = ["·"] * self.SLOTS
        for hour in (0, 6, 12, 18, 23):
            axis[hour] = str(hour % 10)
        text.append("".join(axis), style=_style_for("muted"))
        return text


class RankedBar(_CardBase):
    """Top-N ranked horizontal bars: ``name | bar | messaged/total``.

    Rows are sorted by ``messaged`` descending and clipped to ``max_rows``.
    """

    def __init__(
        self,
        label: str,
        rows: tuple[tuple[str, int, int], ...] = (),
        max_rows: int = 5,
        bar_width: int = 16,
        name_width: int = 18,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._rows = rows
        self._max_rows = max_rows
        self._bar_width = bar_width
        self._name_width = name_width
        self._rendered = self._build()

    def set_data(self, rows: tuple[tuple[str, int, int], ...]) -> None:
        self._rows = rows
        self._refresh_content()

    def _build(self) -> Text:
        text = Text()
        text.append(self._label, style=_style_for("primary"))
        text.append("\n")
        if not self._rows:
            text.append("(no data)", style=_style_for("muted"))
            return text

        top = sorted(self._rows, key=lambda r: r[1], reverse=True)[: self._max_rows]
        bar_width = max(self._bar_width, 1)
        for i, (name, messaged, total) in enumerate(top):
            if i > 0:
                text.append("\n")
            clipped = name[: self._name_width].ljust(self._name_width)
            text.append(clipped, style=_style_for("primary"))
            text.append(" ")
            if total <= 0:
                filled = 0
            else:
                proportion = max(0, min(messaged, total)) / total
                filled = min(bar_width, int(round(proportion * bar_width)))
            text.append(_BAR_FILL * filled, style=_style_for("success"))
            text.append(_BAR_EMPTY * (bar_width - filled), style=_style_for("muted"))
            text.append("  ")
            text.append(
                f"{_format_int(messaged)}/{_format_int(total)}",
                style=_style_for("accent"),
            )
        return text


class AccountDot(_CardBase):
    """One-line account status: ``● name  12.3/hr  5m ago``.

    ``last_sent`` is a caller-formatted relative string ("5m ago", "2h ago");
    the widget does not parse timestamps.
    """

    DEFAULT_CSS = """
    AccountDot {
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        name: str = "",
        active: bool = False,
        sends_per_hour: float = 0.0,
        last_sent: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._name = name
        self._active = active
        self._sends_per_hour = sends_per_hour
        self._last_sent = last_sent
        self._rendered = self._build()

    def set_data(
        self,
        name: str,
        active: bool,
        sends_per_hour: float,
        last_sent: str | None,
    ) -> None:
        self._name = name
        self._active = active
        self._sends_per_hour = sends_per_hour
        self._last_sent = last_sent
        self._refresh_content()

    def _build(self) -> Text:
        text = Text()
        dot = _DOT_ACTIVE if self._active else _DOT_IDLE
        dot_style = _style_for("success") if self._active else _style_for("muted")
        text.append(dot, style=dot_style)
        text.append(" ")
        text.append(self._name or "(unnamed)", style=_style_for("primary"))
        text.append("  ")
        text.append(f"{self._sends_per_hour:.1f}/hr", style=_style_for("accent"))
        text.append("  ")
        text.append(self._last_sent or "—", style=_style_for("muted"))
        return text
