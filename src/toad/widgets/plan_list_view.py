"""PlanListView — renders plan rows from orchestrator state."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from toad.widgets.orchestrator_state import (
    OrchestratorStateWidget,
    PlanSummary,
)

log = logging.getLogger(__name__)


def _elapsed(started_at: str) -> str:
    """Return human-readable elapsed time from an ISO timestamp."""
    if not started_at:
        return ""
    try:
        start = datetime.fromisoformat(started_at)
        now = datetime.now(tz=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        delta = now - start
        secs = int(delta.total_seconds())
        if secs < 0:
            return "0s"
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m {secs % 60}s"
        hours = mins // 60
        return f"{hours}h {mins % 60}m"
    except (ValueError, TypeError):
        return ""


def _status_icon(status: str) -> str:
    """Map plan status to a single-char indicator."""
    return {
        "running": "▶",
        "done": "✓",
        "failed": "✗",
        "reviewing": "⊙",
    }.get(status, "·")


class PlanRow(Static):
    """A single selectable row representing one plan."""

    DEFAULT_CSS = """
    PlanRow {
        height: auto;
        padding: 0 1;
        color: $text;
    }
    PlanRow:hover {
        background: $boost;
    }
    PlanRow.selected {
        background: $accent 20%;
        text-style: bold;
    }
    """

    def __init__(self, plan: PlanSummary, **kwargs) -> None:
        super().__init__(**kwargs)
        self.plan = plan

    def render(self) -> str:
        p = self.plan.progress
        elapsed = _elapsed(self.plan.started_at)
        icon = _status_icon(self.plan.status)
        counts = (
            f"done={p.done} run={p.running} "
            f"queue={p.queued} fail={p.failed}"
        )
        elapsed_str = f"  [{elapsed}]" if elapsed else ""
        return f"{icon} {self.plan.slug}  ({counts}){elapsed_str}"


class PlanListView(Widget, can_focus=True):
    """Renders a list of orchestrator plans from PlanSummary data.

    Listens for :class:`OrchestratorStateWidget.PlansUpdated` messages
    and re-renders. Posts :class:`PlanSelected` when the user clicks a
    plan row.
    """

    class PlanSelected(Message):
        """Posted when a plan row is clicked."""

        def __init__(self, slug: str) -> None:
            super().__init__()
            self.slug = slug

    plans: reactive[list[PlanSummary]] = reactive(
        list, always_update=True
    )

    DEFAULT_CSS = """
    PlanListView {
        height: 1fr;
    }
    PlanListView VerticalScroll {
        height: 1fr;
    }
    PlanListView .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2 1;
        text-align: center;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected_slug: str | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(
                "No orchestrator data",
                classes="empty-state",
                id="plan-list-empty",
            )

    def on_orchestrator_state_widget_plans_updated(
        self, event: OrchestratorStateWidget.PlansUpdated
    ) -> None:
        """Handle upstream plan data updates."""
        self.plans = event.plans

    def watch_plans(self, plans: list[PlanSummary]) -> None:
        """Re-render plan rows when data changes."""
        container = self.query_one(VerticalScroll)
        container.remove_children()

        if not plans:
            container.mount(
                Static(
                    "No orchestrator data",
                    classes="empty-state",
                    id="plan-list-empty",
                )
            )
            return

        for plan in plans:
            row = PlanRow(plan, id=f"plan-row-{plan.slug}")
            if plan.slug == self._selected_slug:
                row.add_class("selected")
            container.mount(row)

        # Auto-select first plan if none selected
        if self._selected_slug is None and plans:
            self._select(plans[0].slug)

    def on_click(self, event) -> None:
        """Handle click on a plan row."""
        widget = event.widget if hasattr(event, "widget") else None
        # Walk up to find a PlanRow
        target = widget
        while target is not None and not isinstance(target, PlanRow):
            target = target.parent
        if isinstance(target, PlanRow):
            self._select(target.plan.slug)

    def _select(self, slug: str) -> None:
        """Mark a plan as selected and post the message."""
        self._selected_slug = slug
        for row in self.query(PlanRow):
            row.remove_class("selected")
            if row.plan.slug == slug:
                row.add_class("selected")
        self.post_message(self.PlanSelected(slug))
