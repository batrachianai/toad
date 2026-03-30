"""WorkerListView — renders work items for the selected orchestrator plan."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from toad.widgets.orchestrator_state import (
    OrchestratorStateWidget,
    PlanItem,
)

log = logging.getLogger(__name__)

STATUS_BADGES: dict[str, str] = {
    "done": "[green]DONE[/]",
    "running": "[yellow bold]RUN[/]",
    "queued": "[dim]QUEUE[/]",
    "failed": "[red bold]FAIL[/]",
    "reviewing": "[cyan]REVIEW[/]",
}


def _badge(status: str) -> str:
    """Return a Rich-markup status badge."""
    return STATUS_BADGES.get(status, f"[dim]{status.upper()}[/]")


def _render_item(item: PlanItem) -> str:
    """Format a single plan item as a Rich-markup line."""
    desc = item.description
    if len(desc) > 60:
        desc = desc[:57] + "..."
    iteration = f"iter {item.iteration}/{item.max_iterations}"
    return (
        f"  {item.id:>3}  {_badge(item.status):8s}  "
        f"{iteration:10s}  {desc}"
    )


class WorkerListView(Widget, can_focus=True):
    """Displays work items for the currently selected plan.

    Listens to :class:`OrchestratorStateWidget.ItemsUpdated` messages
    to refresh the item list. Shows an empty-state label when no items
    are available.
    """

    DEFAULT_CSS = """
    WorkerListView {
        height: 1fr;
    }
    WorkerListView VerticalScroll {
        height: 1fr;
    }
    WorkerListView .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2 1;
        text-align: center;
    }
    WorkerListView .header-row {
        color: $text-muted;
        text-style: bold;
        padding: 0 0 0 1;
    }
    WorkerListView .item-row {
        padding: 0 0 0 1;
    }
    WorkerListView .item-running {
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(
                "Select a plan to view workers",
                classes="empty-state",
                id="workers-empty-label",
            )

    def on_orchestrator_state_widget_items_updated(
        self,
        event: OrchestratorStateWidget.ItemsUpdated,
    ) -> None:
        """Refresh item list when the selected plan's items change."""
        self._render_items(event.items)

    def _render_items(self, items: list[PlanItem]) -> None:
        """Rebuild the item list from scratch."""
        scroll = self.query_one(VerticalScroll)
        scroll.remove_children()

        if not items:
            scroll.mount(
                Static(
                    "No items for this plan",
                    classes="empty-state",
                    id="workers-empty-label",
                )
            )
            return

        header = "   ID  Status    Iteration   Description"
        scroll.mount(Static(header, classes="header-row"))

        for item in items:
            classes = "item-row"
            if item.status == "running":
                classes += " item-running"
            scroll.mount(
                Static(_render_item(item), classes=classes)
            )
