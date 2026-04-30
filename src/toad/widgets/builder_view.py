"""BuilderView — status bar, scrollable logs, metrics grid."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from toad.widgets.canon_state import (
    CanonState,
    CanonStateWidget,
    LogEntry,
)
from toad.widgets.pipeline_view import PipelineView

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


# Core writes raw metric keys (cycles, signals, markets, …) into
# state.metrics. The TUI applies these aliases at render time so the
# panel reads naturally even before core renames the keys. When core
# updates the key, drop the alias here.
METRIC_LABEL_ALIASES: dict[str, str] = {
    "cycles": "Runs",
    "runs": "Runs",
    "signals": "Opportunities",
    "opportunities": "Opportunities",
    "games": "Games",
    "markets": "Markets",
    "errors": "Errors",
    "mode": "Mode",
}


def _humanize_metric_key(raw: str) -> str:
    """Map a core-written metric key to its user-facing label."""
    aliased = METRIC_LABEL_ALIASES.get(raw.lower())
    if aliased is not None:
        return aliased
    # Fallback: turn snake_case / kebab-case into Title Case so unknown
    # keys still look intentional.
    return raw.replace("_", " ").replace("-", " ").strip().title() or raw


def _status_bar(phase: str, status: str) -> str:
    """Render phase + status as a single-line bar."""
    phase_color = PHASE_COLORS.get(phase, "dim")
    status_color = STATUS_COLORS.get(status, "dim")
    phase_text = f"[{phase_color} bold]{phase.upper()}[/]"
    status_text = f"[{status_color}] {status.upper()} [/]"
    return f"  Phase: {phase_text}    Status: {status_text}"


def _render_log(entry: LogEntry, *, now: datetime | None = None) -> str:
    """Format a single log entry with level-based coloring.

    Timestamp renders friendly: "just now" / "12s ago" / "4m ago" /
    "17:12" / "Apr 30 17:12" depending on age. Falls back to the raw
    timestamp's last 8 chars if it can't be parsed as ISO.
    """
    color = LOG_LEVEL_COLORS.get(entry.level, "white")
    ts = _format_friendly_timestamp(entry.timestamp, now=now)
    ts_markup = f"[dim]{ts:<10}[/] " if ts else ""
    return f"  {ts_markup}[{color}]{entry.message}[/]"


def _format_friendly_timestamp(
    raw: str, *, now: datetime | None = None
) -> str:
    """Convert an ISO timestamp into a human-friendly relative/clock label."""
    if not raw:
        return ""
    parsed = _parse_iso(raw)
    if parsed is None:
        # Last-resort: trim long timestamps to HH:MM:SS so the column stays narrow.
        return raw[-8:] if len(raw) >= 8 else raw
    current = now or datetime.now(timezone.utc)
    delta = (current - parsed).total_seconds()
    if delta < 5:
        return "just now"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return parsed.astimezone().strftime("%H:%M")
    return parsed.astimezone().strftime("%b %d %H:%M")


def _parse_iso(raw: str) -> datetime | None:
    text = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _render_metrics(metrics: tuple[tuple[str, object], ...]) -> str:
    """Render metrics as a key-value grid with humanised labels."""
    if not metrics:
        return "  [dim]No metrics[/]"
    lines: list[str] = []
    pairs = [(_humanize_metric_key(k), v) for k, v in metrics]
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
        yield PipelineView(id="builder-pipeline")
        # Stats live above the log so all the headline state (phase,
        # status, pipeline, counts) sits at the top of the view; the
        # log scrolls underneath.
        yield Static("[dim]  No metrics[/]", id="builder-metrics")
        with VerticalScroll():
            yield Static(
                "Waiting for build activity…",
                classes="empty-state",
                id="builder-empty-label",
            )

    async def on_canon_state_widget_canon_state_updated(
        self,
        event: CanonStateWidget.CanonStateUpdated,
    ) -> None:
        """Refresh view when canon state changes."""
        await self._render_state(event.state)

    async def _render_state(self, state: CanonState) -> None:
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

        # Pipeline flow
        pipeline = self.query_one("#builder-pipeline", PipelineView)
        await pipeline.render_flow(state.flow)

        # Logs
        scroll = self.query_one(VerticalScroll)
        await scroll.remove_children()

        logs = state.logs[-MAX_LOG_LINES:]
        if not logs:
            await scroll.mount(
                Static(
                    "No build logs",
                    classes="empty-state",
                    id="builder-empty-label",
                )
            )
        else:
            # Reverse so the newest entry sits at the top of the scroll
            # area; older entries scroll down. The scroll position stays
            # at home (0,0) by default which keeps the most recent line
            # visible without yanking the user back when new lines land.
            now = datetime.now(timezone.utc)
            widgets = [
                Static(_render_log(entry, now=now)) for entry in reversed(logs)
            ]
            await scroll.mount_all(widgets)
            scroll.scroll_home(animate=False)

        # Metrics
        metrics_widget = self.query_one("#builder-metrics", Static)
        metrics_widget.update(_render_metrics(state.metrics))
