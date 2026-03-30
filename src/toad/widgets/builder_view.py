"""BuilderView — phase badge, iteration, scrollable logs, error banner."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from toad.widgets.canon_state import (
    BUILD_PHASES,
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

LOG_LEVEL_COLORS: dict[str, str] = {
    "error": "red bold",
    "warn": "yellow",
    "warning": "yellow",
    "info": "white",
    "debug": "dim",
}


def _phase_badge(phase: str) -> str:
    """Return a Rich-markup phase badge."""
    color = PHASE_COLORS.get(phase, "dim")
    return f"[{color}] {phase.upper()} [/]"


def _render_log(entry: LogEntry) -> str:
    """Format a single log entry with level-based coloring."""
    color = LOG_LEVEL_COLORS.get(entry.level, "white")
    ts = f"[dim]{entry.timestamp}[/] " if entry.timestamp else ""
    tag = f"[{color}]{entry.level.upper():>5s}[/]"
    return f"  {ts}{tag}  {entry.message}"


class BuilderView(Widget, can_focus=True):
    """Displays canon builder state: phase, iteration, logs, errors.

    Listens to :class:`CanonStateWidget.CanonStateUpdated` messages
    and re-renders when the phase is a build phase.
    """

    DEFAULT_CSS = """
    BuilderView {
        height: 1fr;
    }
    BuilderView #builder-header {
        height: auto;
        padding: 0 1;
    }
    BuilderView #builder-error {
        display: none;
        height: auto;
        padding: 0 1;
        background: $error 20%;
        color: $text;
        text-style: bold;
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
    BuilderView .log-row {
        padding: 0 0 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="builder-header")
        yield Static(id="builder-error")
        with VerticalScroll():
            yield Static(
                "No build activity",
                classes="empty-state",
                id="builder-empty-label",
            )

    def on_canon_state_widget_canon_state_updated(
        self,
        event: CanonStateWidget.CanonStateUpdated,
    ) -> None:
        """Refresh view when canon state changes."""
        self._render_state(event.state)

    def _render_state(self, state: CanonState) -> None:
        """Rebuild the builder view from canon state."""
        # Header: phase badge + iteration
        header = self.query_one("#builder-header", Static)
        if state.phase in BUILD_PHASES:
            badge = _phase_badge(state.phase)
            header.update(
                f"{badge}  Iteration [bold]{state.iteration}[/]"
            )
        else:
            header.update("[dim]Builder idle[/]")

        # Error banner
        error_widget = self.query_one("#builder-error", Static)
        if state.status == "error" and state.error:
            error_widget.update(f"[red bold]ERROR:[/] {state.error}")
            error_widget.display = True
        else:
            error_widget.display = False

        # Logs — cap at MAX_LOG_LINES, most recent last
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
            return

        for entry in logs:
            scroll.mount(
                Static(_render_log(entry), classes="log-row")
            )
