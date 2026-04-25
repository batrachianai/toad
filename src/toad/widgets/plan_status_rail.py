"""PlanStatusRail — compact footer strip for one plan.

Renders one status glyph per plan item followed by an overall verdict
badge (running / SHIP / REVISE). The rail is "dumb": the owning
``PlanExecutionTab`` passes items in at construction, calls
:meth:`set_items` / :meth:`set_verdict` when ``PlanExecutionModel`` emits
updates, or posts :class:`PlanStatusRail.ItemStatusChanged` to flip a
single glyph without rebuilding the rail. No file I/O happens here.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


__all__ = [
    "STATUS_COLORS",
    "STATUS_GLYPHS",
    "VERDICT_COLORS",
    "PlanStatusRail",
    "RailItem",
]


STATUS_COLORS: dict[str, str] = {
    "queued": "grey50",
    "ready": "cyan",
    "running": "yellow",
    "done": "green",
    "failed": "red",
    "review": "magenta",
}

STATUS_GLYPHS: dict[str, str] = {
    "queued": "○",
    "ready": "◐",
    "running": "◉",
    "done": "✓",
    "failed": "✗",
    "review": "?",
}

VERDICT_COLORS: dict[str, str] = {
    "running": "yellow",
    "SHIP": "green",
    "REVISE": "red",
}

_FALLBACK_COLOR = "white"
_FALLBACK_GLYPH = "•"
_VERDICT_SEPARATOR = "  "


@dataclass(frozen=True)
class RailItem:
    """A single plan item on the rail."""

    id: int
    status: str


class PlanStatusRail(Static):
    """Compact per-item glyph strip plus verdict badge."""

    DEFAULT_CSS = """
    PlanStatusRail {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    """

    verdict: reactive[str] = reactive("running", init=False)

    class ItemStatusChanged(Message):
        """Posted by the model to flip a single item's status."""

        def __init__(self, item_id: int, status: str) -> None:
            super().__init__()
            self.item_id = item_id
            self.status = status

    def __init__(
        self,
        items: list[RailItem] | None = None,
        *,
        verdict: str = "running",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._items: list[RailItem] = list(items) if items else []
        self.set_reactive(PlanStatusRail.verdict, verdict)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_items(self, items: list[RailItem]) -> None:
        """Replace the rail's items and re-render."""
        self._items = list(items)
        self.refresh()

    def set_verdict(self, verdict: str) -> None:
        """Update the verdict badge (triggers a re-render via reactive)."""
        self.verdict = verdict

    def glyphs_plain(self) -> list[str]:
        """Plain glyphs in render order — useful for assertions."""
        return [STATUS_GLYPHS.get(i.status, _FALLBACK_GLYPH) for i in self._items]

    def has_color_for(self, item_id: int, color: str) -> bool:
        """Whether the glyph for ``item_id`` paints ``color``."""
        position = self._index_of(item_id)
        if position is None:
            return False
        return self._span_at_has_color(position, color)

    def verdict_label(self) -> str:
        """Current verdict string."""
        return self.verdict

    def verdict_has_color(self, color: str) -> bool:
        """Whether the verdict badge paints ``color``."""
        label = self._build_label()
        badge_start = label.plain.rfind(self.verdict)
        if badge_start < 0:
            return False
        for span in label.spans:
            if span.start <= badge_start < span.end and color in str(span.style):
                return True
        return False

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_plan_status_rail_item_status_changed(
        self, event: ItemStatusChanged
    ) -> None:
        """Flip a single item's status in place."""
        position = self._index_of(event.item_id)
        if position is None:
            return
        existing = self._items[position]
        self._items[position] = RailItem(id=existing.id, status=event.status)
        self.refresh()

    # ------------------------------------------------------------------
    # Reactive hooks
    # ------------------------------------------------------------------

    def watch_verdict(self, _old: str, _new: str) -> None:
        self.refresh()

    def render(self) -> Text:
        return self._build_label()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _index_of(self, item_id: int) -> int | None:
        for index, item in enumerate(self._items):
            if item.id == item_id:
                return index
        return None

    def _build_label(self) -> Text:
        label = Text()
        for index, item in enumerate(self._items):
            glyph = STATUS_GLYPHS.get(item.status, _FALLBACK_GLYPH)
            color = STATUS_COLORS.get(item.status, _FALLBACK_COLOR)
            if index > 0:
                label.append(" ")
            label.append(glyph, style=color)
        label.append(_VERDICT_SEPARATOR)
        verdict = self.verdict
        verdict_color = VERDICT_COLORS.get(verdict, _FALLBACK_COLOR)
        label.append(verdict, style=f"bold {verdict_color}")
        return label

    def _span_at_has_color(self, position: int, color: str) -> bool:
        label = self._build_label()
        # Glyphs are single characters separated by a space; index maps to
        # char offset ``position * 2`` within the glyph run.
        offset = position * 2
        for span in label.spans:
            if span.start <= offset < span.end and color in str(span.style):
                return True
        return False
