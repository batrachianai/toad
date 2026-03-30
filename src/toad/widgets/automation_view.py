"""AutomationView — status badge, metrics grid, scrollable logs, error banner."""

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

STATUS_COLORS: dict[str, str] = {
    "running": "green",
    "idle": "dim",
    "error": "red bold",
    "paused": "yellow",
}

LOG_LEVEL_COLORS: dict[str, str] = {
    "error": "red bold",
    "warn": "yellow",
    "warning": "yellow",
    "info": "white",
    "debug": "dim",
}


def _status_badge(status: str) -> str:
    """Return Rich-markup status badge."""
    color = STATUS_COLORS.get(status, "dim")
    return f"[{color}]{status.upper()}[/]"


def _render_metric(key: str, value: str) -> str:
    """Format a single metric as a Rich-markup line."""
    return f"  [bold]{key}[/]: {value}"


def _render_log(entry: LogEntry) -> str:
    """Format a log entry with color coding by level."""
    color = LOG_LEVEL_COLORS.get(entry.level, "white")
    ts = f"[dim]{entry.timestamp}[/] " if entry.timestamp else ""
    level_tag = f"[{color}]{entry.level.upper():>5s}[/]"
    return f"{ts}{level_tag} {entry.message}"


class AutomationView(Widget, can_focus=True):
    """Displays canon automation state: status, metrics, logs, errors.

    Listens to :class:`CanonStateWidget.CanonStateUpdated` messages
    and re-renders when the canon state changes. Shows an empty-state
    label when no automation data is available.
    """

    DEFAULT_CSS = """
    AutomationView {
        height: 1fr;
    }
    AutomationView VerticalScroll {
        height: 1fr;
    }
    AutomationView .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2 1;
        text-align: center;
    }
    AutomationView .status-bar {
        padding: 0 1;
        height: auto;
    }
    AutomationView .metrics-header {
        color: $text-muted;
        text-style: bold;
        padding: 1 1 0 1;
    }
    AutomationView .metric-row {
        padding: 0 1;
    }
    AutomationView .logs-header {
        color: $text-muted;
        text-style: bold;
        padding: 1 1 0 1;
    }
    AutomationView .log-line {
        padding: 0 1;
    }
    AutomationView .error-banner {
        background: $error 30%;
        color: $text;
        text-style: bold;
        padding: 0 1;
        margin: 1 0 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(
                "No automation data",
                classes="empty-state",
                id="automation-empty-label",
            )

    def on_canon_state_widget_canon_state_updated(
        self,
        event: CanonStateWidget.CanonStateUpdated,
    ) -> None:
        """Refresh view when canon state changes."""
        self._render_state(event.state)

    def _render_state(self, state: CanonState) -> None:
        """Rebuild the automation view from current state."""
        scroll = self.query_one(VerticalScroll)
        scroll.remove_children()

        if not state.phase:
            scroll.mount(
                Static(
                    "No automation data",
                    classes="empty-state",
                    id="automation-empty-label",
                )
            )
            return

        # Status badge
        scroll.mount(
            Static(
                f"Status: {_status_badge(state.status)}",
                classes="status-bar",
            )
        )

        # Metrics grid
        if state.metrics:
            scroll.mount(
                Static("Metrics", classes="metrics-header")
            )
            for key, value in state.metrics:
                scroll.mount(
                    Static(
                        _render_metric(key, value),
                        classes="metric-row",
                    )
                )

        # Scrollable logs (capped at MAX_LOG_LINES)
        if state.logs:
            scroll.mount(
                Static("Logs", classes="logs-header")
            )
            recent = state.logs[-MAX_LOG_LINES:]
            for entry in recent:
                scroll.mount(
                    Static(
                        _render_log(entry),
                        classes="log-line",
                    )
                )

        # Error banner
        if state.error:
            scroll.mount(
                Static(
                    f"ERROR: {state.error}",
                    classes="error-banner",
                    id="automation-error-banner",
                )
            )
