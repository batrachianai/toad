"""BuilderView — status bar, scrollable logs, metrics grid."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from toad.widgets.canon_state import (
    CanonState,
    CanonStateWidget,
    LogEntry,
)

log = logging.getLogger(__name__)

MAX_LOG_LINES = 50

PHASE_COLORS: dict[str, str] = {
    "init": "cyan",
    "scaffold": "blue",
    "strategy": "magenta",
    "develop": "yellow",
}

STATUS_COLORS: dict[str, str] = {
    "running": "green",
    "idle": "dim",
    "complete": "green bold",
    "error": "red bold",
    "paused": "yellow",
    "executing": "magenta",
    "automating": "cyan",
}

LOG_LEVEL_COLORS: dict[str, str] = {
    "error": "red bold",
    "warn": "yellow",
    "warning": "yellow",
    "info": "white",
    "debug": "dim",
}


def _status_bar(phase: str, status: str) -> str:
    """Render phase + status as a single-line bar."""
    phase_color = PHASE_COLORS.get(phase, "dim")
    status_color = STATUS_COLORS.get(status, "dim")
    phase_text = f"[{phase_color} bold]{phase.upper()}[/]"
    status_text = f"[{status_color}] {status.upper()} [/]"
    return f"  Phase: {phase_text}    Status: {status_text}"


def _render_log(entry: LogEntry) -> str:
    """Format a single log entry with level-based coloring."""
    color = LOG_LEVEL_COLORS.get(entry.level, "white")
    ts = entry.timestamp[-8:] if entry.timestamp else ""
    ts_markup = f"[dim]{ts}[/] " if ts else ""
    return f"  {ts_markup}[{color}]{entry.message}[/]"


def _render_metrics(metrics: tuple[tuple[str, object], ...]) -> str:
    """Render metrics as a key-value grid."""
    if not metrics:
        return "  [dim]No metrics[/]"
    lines: list[str] = []
    pairs = list(metrics)
    for i in range(0, len(pairs), 2):
        k1, v1 = pairs[i]
        left = f"  [bold]{k1}:[/] {v1}"
        if i + 1 < len(pairs):
            k2, v2 = pairs[i + 1]
            right = f"    [bold]{k2}:[/] {v2}"
            lines.append(f"{left:<40s}{right}")
        else:
            lines.append(left)
    return "\n".join(lines)


class BuilderView(Widget, can_focus=True):
    """Displays canon builder state: status bar, logs, metrics.

    Listens to :class:`CanonStateWidget.CanonStateUpdated` messages
    and re-renders when the phase is a build phase.
    """

    DEFAULT_CSS = """
    BuilderView {
        height: 1fr;
    }
    BuilderView #builder-status-bar {
        height: auto;
        padding: 1 0;
        background: $surface;
    }
    BuilderView #builder-error {
        display: none;
        height: auto;
        padding: 0 1;
        background: $error 20%;
        color: $text;
        text-style: bold;
    }
    BuilderView #builder-metrics {
        height: auto;
        padding: 1 0;
        background: $surface;
    }
    BuilderView VerticalScroll {
        height: 1fr;
    }
    BuilderView .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2 1;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "  [dim]Phase:[/] —    [dim]Status:[/] —",
            id="builder-status-bar",
        )
        yield Static(id="builder-error")
        with VerticalScroll():
            yield Static(
                "Waiting for build activity…",
                classes="empty-state",
                id="builder-empty-label",
            )
        yield Static("[dim]  No metrics[/]", id="builder-metrics")

    def on_canon_state_widget_canon_state_updated(
        self,
        event: CanonStateWidget.CanonStateUpdated,
    ) -> None:
        """Refresh view when canon state changes."""
        self._render_state(event.state)

    def _render_state(self, state: CanonState) -> None:
        """Rebuild the builder view from canon state."""
        # Status bar: phase + status
        status_bar = self.query_one("#builder-status-bar", Static)
        status_bar.update(_status_bar(state.phase, state.status))

        # Error banner
        error_widget = self.query_one("#builder-error", Static)
        if state.status == "error" and state.error:
            error_widget.update(
                f"[red bold]ERROR:[/] {state.error}"
            )
            error_widget.display = True
        else:
            error_widget.display = False

        # Logs
        scroll = self.query_one(VerticalScroll)
        scroll.remove_children()

        logs = state.logs[-MAX_LOG_LINES:]
        if not logs:
            scroll.mount(
                Static(
                    "No build logs",
                    classes="empty-state",
                    id="builder-empty-label",
                )
            )
        else:
            for entry in logs:
                scroll.mount(Static(_render_log(entry)))

        # Metrics
        metrics_widget = self.query_one("#builder-metrics", Static)
        metrics_widget.update(_render_metrics(state.metrics))
