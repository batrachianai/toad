"""GitHubStateWidget — PM dashboard: status overview, timeline, detail tabs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Collapsible, Static

from toad.widgets.gantt_timeline import GanttTimeline
from toad.widgets.github_views.fetch import (
    RepoInfo,
    check_auth,
    detect_repo_from_path,
)
from toad.widgets.github_views.issues import IssuesView
from toad.widgets.github_views.plans import PlansView
from toad.widgets.github_views.prs import PRsView
from toad.widgets.github_views.status_overview import StatusOverview
from toad.widgets.github_views.timeline import TimelineView

log = logging.getLogger(__name__)


class GitHubStateWidget(Widget, can_focus=True):
    """GitHub project state — PM dashboard layout."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
    ]

    DEFAULT_CSS = """
    GitHubStateWidget {
        height: 1fr;
    }
    GitHubStateWidget VerticalScroll {
        height: 1fr;
    }
    GitHubStateWidget .gh-error {
        color: $error;
        text-style: italic;
        padding: 1;
    }
    GitHubStateWidget .section-label {
        color: $text-muted;
        text-style: bold;
        padding: 1 1 0 1;
    }
    GitHubStateWidget Collapsible {
        padding: 0 1;
    }
    GitHubStateWidget .section-title {
        color: $text-warning;
        text-style: bold;
        padding: 1 1 0 1;
    }
    """

    def __init__(
        self,
        repo: RepoInfo | None = None,
        project_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._repo = repo
        self._project_path = project_path

    def _gantt_path(self) -> Path | None:
        """Resolve timeline.json from the project directory."""
        project_dir = Path(self._project_path or ".")
        path = project_dir / "timeline.json"
        return path if path.exists() else None

    def compose(self) -> ComposeResult:
        gantt_path = self._gantt_path()
        with VerticalScroll():
            yield StatusOverview(id="gh-status-overview")
            if gantt_path:
                yield GanttTimeline(data_path=gantt_path, id="gh-gantt")
            yield Static("Plans", classes="section-title")
            yield PlansView(id="gh-plans")
            yield Static("Pull Requests", classes="section-title")
            yield PRsView(id="gh-prs")
            with Collapsible(title="Timeline", collapsed=True):
                yield TimelineView(id="gh-timeline")

    async def on_mount(self) -> None:
        """Detect repo and load initial data."""
        if self._repo is None:
            try:
                path = self._project_path or "."
                self._repo = await detect_repo_from_path(path)
            except Exception as exc:
                log.warning("Could not detect repo: %s", exc)
                self._show_error(
                    "Could not detect GitHub repo — "
                    "ensure you are in a git repo with a GitHub remote"
                )
                return

        authenticated = await check_auth()
        if not authenticated:
            self._show_error("Not authenticated — run: gh auth login")
            return

        await self._load_all()

    async def _load_all(self) -> None:
        """Load data into all views."""
        if self._repo is None:
            return

        overview = self.query_one("#gh-status-overview", StatusOverview)
        timeline = self.query_one("#gh-timeline", TimelineView)
        plans = self.query_one("#gh-plans", PlansView)
        prs = self.query_one("#gh-prs", PRsView)

        # Reload Gantt on refresh if present
        try:
            gantt = self.query_one("#gh-gantt", GanttTimeline)
            gantt_path = self._gantt_path()
            if gantt_path:
                gantt.reload_from_file(gantt_path)
        except Exception:
            pass

        await overview.load(self._repo)
        await plans.load(self._repo)
        await prs.load(self._repo)
        await timeline.load(self._repo)

    async def refresh_data(self) -> None:
        """Re-fetch data for all views."""
        await self._load_all()

    async def action_refresh(self) -> None:
        """Handle the 'r' keybinding to refresh all GitHub data."""
        log.info("Refreshing GitHub data")
        await self._load_all()

    def _show_error(self, message: str) -> None:
        """Display an error message, hiding the main content."""
        scroll = self.query_one(VerticalScroll)
        scroll.display = False
        self.mount(Static(message, classes="gh-error"))
