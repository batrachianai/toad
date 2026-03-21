"""Timeline — chronological plan lifecycle events with colored badges."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from toad.widgets.github_views.fetch import (
    GitHubAuthError,
    GitHubFetchError,
    RepoInfo,
    fetch_all_plan_issues,
)

log = logging.getLogger(__name__)

LABEL_COLORS: dict[str, str] = {
    "plan:draft": "bright_black",
    "plan:active": "green",
    "plan:pr-review": "dodger_blue",
    "plan:completed": "medium_purple",
    "plan:failed": "red",
}


def _plan_label(issue: dict[str, Any]) -> str | None:
    """Extract the first plan:* label name from an issue."""
    for lbl in issue.get("labels", []):
        name = lbl.get("name", "")
        if name.startswith("plan:"):
            return name
    return None


def _label_badge(label: str) -> Text:
    """Build a Rich Text badge with the label's color."""
    color = LABEL_COLORS.get(label, "white")
    return Text(label, style=color)


def _relative_time(iso_ts: str) -> str:
    """Convert an ISO 8601 timestamp to a human-friendly relative string."""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return iso_ts[:10] if iso_ts else "?"
    delta = datetime.now(tz=timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


class TimelineView(Static):
    """Chronological list of plan lifecycle events with colored badges."""

    DEFAULT_CSS = """
    TimelineView {
        height: auto;
        max-height: 20;
    }
    TimelineView DataTable {
        height: auto;
        max-height: 18;
    }
    TimelineView .error-label {
        color: $error;
        padding: 1;
    }
    TimelineView .empty-label {
        color: $text-muted;
        text-style: italic;
        padding: 1;
    }
    """

    def __init__(
        self,
        repo: RepoInfo | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._repo = repo

    def compose(self) -> ComposeResult:
        table = DataTable(id="timeline-table")
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Updated", "#", "Title", "Status")
        yield table

    async def load(self, repo: RepoInfo | None = None) -> None:
        """Fetch plan issues and populate the timeline."""
        if repo is not None:
            self._repo = repo
        if self._repo is None:
            return

        table = self.query_one("#timeline-table", DataTable)
        table.clear()

        try:
            issues = await fetch_all_plan_issues(self._repo)
        except GitHubAuthError:
            table.display = False
            await self.mount(
                Static(
                    "Not authenticated -- run: gh auth login",
                    classes="error-label",
                )
            )
            return
        except GitHubFetchError as exc:
            log.warning("timeline fetch failed: %s", exc)
            table.display = False
            await self.mount(
                Static(f"Fetch error: {exc}", classes="error-label")
            )
            return

        if not issues:
            table.display = False
            await self.mount(
                Static("No plan issues found", classes="empty-label")
            )
            return

        # Sort by updatedAt descending (most recent first)
        issues.sort(
            key=lambda i: i.get("updatedAt", ""),
            reverse=True,
        )

        for issue in issues:
            label = _plan_label(issue)
            badge = _label_badge(label) if label else Text("--")
            when = _relative_time(issue.get("updatedAt", ""))
            number = f"#{issue.get('number', '')}"
            title = issue.get("title", "")
            table.add_row(when, number, title, badge)
