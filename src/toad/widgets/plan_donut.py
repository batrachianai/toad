"""PlanDonut — compact 2-row progress gauge for the plan-execution header.

Two-row stacked layout:

- Row 0 — segmented bar of fixed width. Each cell is coloured by the
  plan item it represents (proportional mapping from cell index to
  item index), so a glance at the bar shows the run's overall
  composition: how many done, running, queued, failed.
- Row 1 — bold percentage centered under the bar (``done/total``).

Despite the historical class name (the first cut was a circular donut)
the widget is now a horizontal gauge — terminal cells aren't square so
a real ring rendered poorly. The flat bar reads cleanly at any zoom.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text
from textual.widgets import Static

from toad.widgets.plan_dep_graph import DepGraphItem
from toad.widgets.plan_status_rail import STATUS_COLORS


__all__ = ["PlanDonut"]


_BAR_WIDTH = 12
_BAR_GLYPH = "█"
_EMPTY_GLYPH = "·"
_EMPTY_COLOR = "grey30"
_FALLBACK_COLOR = "white"


class PlanDonut(Static):
    """Compact 2-row gauge — segmented bar plus percent label."""

    DEFAULT_CSS = """
    PlanDonut {
        width: 12;
        height: 2;
        background: $panel;
        color: $text;
        padding: 0;
        content-align: center middle;
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
        out.append("\n")
        if total == 0:
            label = "—"
        else:
            pct = round(done * 100 / total)
            label = f"{done}/{total} {pct:>3d}%"
        out.append(label.center(_BAR_WIDTH), style="bold")
        return out
