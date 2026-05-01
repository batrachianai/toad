"""PlanProgress — single-line progress gauge for the plan-execution header.

One row: a 12-cell segmented bar followed by a bold percentage.
Each bar cell is coloured by the plan item it represents (proportional
mapping from cell index to item index), so a glance shows the run's
overall composition — done, running, queued, failed.

The widget started life as a circular donut, then a 2-row stack;
terminal cells aren't square so the ring rendered lopsided, and the
stack ate vertical space the header didn't have to spare. The flat,
inline gauge reads cleanly at any zoom and keeps the header on a
single line.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text
from textual.widgets import Static

from toad.widgets.plan_dep_graph import DepGraphItem
from toad.widgets.plan_status_rail import STATUS_COLORS


__all__ = ["PlanProgress"]


_BAR_WIDTH = 12
_BAR_GLYPH = "█"
_EMPTY_GLYPH = "·"
_EMPTY_COLOR = "grey30"
_FALLBACK_COLOR = "white"
# Bar (12) + space + percent label (up to "100%" = 4) = 17.
_WIDGET_WIDTH = _BAR_WIDTH + 1 + 4


class PlanProgress(Static):
    """Single-line gauge — segmented bar followed by percent label."""

    DEFAULT_CSS = """
    PlanProgress {
        width: 17;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0;
        content-align: left middle;
    }
    """

    def __init__(
        self,
        *,
        items: Sequence[DepGraphItem] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._items: list[DepGraphItem] = list(items) if items else []

    def set_items(self, items: Sequence[DepGraphItem]) -> None:
        """Replace items and re-render."""
        self._items = list(items)
        self.refresh()

    def render(self) -> Text:
        return self._build()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build(self) -> Text:
        total = len(self._items)
        done = sum(1 for it in self._items if it.status == "done")
        out = Text()
        for col in range(_BAR_WIDTH):
            if total == 0:
                out.append(_EMPTY_GLYPH, style=_EMPTY_COLOR)
                continue
            item_index = (col * total) // _BAR_WIDTH
            item = self._items[item_index]
            color = STATUS_COLORS.get(item.status, _FALLBACK_COLOR)
            out.append(_BAR_GLYPH, style=color)
        if total == 0:
            label = "  —"
        else:
            pct = round(done * 100 / total)
            label = f" {pct:>3d}%"
        out.append(label, style="bold")
        return out
