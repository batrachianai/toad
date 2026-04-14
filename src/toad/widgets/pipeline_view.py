"""PipelineView — horizontal flow diagram showing automation cycle steps."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from toad.widgets.canon_state import FlowState

log = logging.getLogger(__name__)


def _label_for(step: str, labels: tuple[tuple[str, str], ...]) -> str:
    """Look up display label for a step id."""
    for key, val in labels:
        if key == step:
            return val
    return step.replace("_", " ").title()


def _step_class(
    step: str,
    active: str,
    completed: tuple[str, ...],
) -> str:
    """Return CSS class string for a step box."""
    if step == active:
        return "step-box step-active"
    if step in completed:
        return "step-box step-done"
    return "step-box step-idle"


class PipelineView(Widget):
    """Renders automation flow as bordered boxes with arrows.

    Listens to :class:`CanonStateWidget.CanonStateUpdated` and
    re-renders when the flow state changes.
    """

    DEFAULT_CSS = """
    PipelineView {
        height: auto;
        padding: 1 1 0 1;
    }
    PipelineView #pipeline-row {
        height: 3;
        align: center middle;
    }
    PipelineView .step-box {
        width: auto;
        height: 3;
        min-width: 12;
        border: round $surface-lighten-2;
        padding: 0 1;
        content-align: center middle;
        color: $text-muted;
    }
    PipelineView .step-active {
        border: round $accent;
        color: $accent;
        text-style: bold;
    }
    PipelineView .step-done {
        border: round $success 60%;
        color: $success 60%;
    }
    PipelineView .step-idle {
        border: round $surface-lighten-2;
        color: $text-muted;
    }
    PipelineView .step-arrow {
        width: 3;
        height: 3;
        content-align: center middle;
        color: $text-muted;
    }
    PipelineView .no-flow {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="pipeline-row"):
            yield Static(
                "[dim]No flow data[/]",
                id="pipeline-placeholder",
            )

    async def render_flow(self, flow: FlowState | None) -> None:
        """Rebuild the pipeline boxes from flow state."""
        row = self.query_one("#pipeline-row", Horizontal)
        await row.remove_children()

        if not flow or not flow.steps:
            await row.mount(
                Static("[dim]No flow data[/]", id="pipeline-placeholder")
            )
            return

        widgets: list[Static] = []
        for i, step in enumerate(flow.steps):
            if i > 0:
                widgets.append(Static(" → ", classes="step-arrow"))

            label = _label_for(step, flow.labels)
            css_class = _step_class(step, flow.active, flow.completed)
            widgets.append(Static(label, classes=css_class))
        await row.mount_all(widgets)
