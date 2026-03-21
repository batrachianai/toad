"""GitHubStateWidget — TabbedContent wrapping 4 GitHub data views."""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Static, TabbedContent, TabPane

from toad.widgets.github_views.fetch import (
    RepoInfo,
    check_auth,
    detect_repo_from_path,
)
from toad.widgets.github_views.issues import IssuesView
from toad.widgets.github_views.plans import PlansView
from toad.widgets.github_views.prs import PRsView
from toad.widgets.github_views.timeline import TimelineView

log = logging.getLogger(__name__)


class GitHubStateWidget(Widget, can_focus=True):
    """GitHub project state panel with Timeline, Issues, Plans, and PRs tabs."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
    ]

    DEFAULT_CSS = """
    GitHubStateWidget {
        height: 1fr;
    }
    GitHubStateWidget TabbedContent {
        height: 1fr;
    }
    GitHubStateWidget .gh-error {
        color: $error;
        text-style: italic;
        padding: 1;
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

    def compose(self) -> ComposeResult:
        with TabbedContent("Timeline", "Issues", "Plans", "PRs"):
            yield TabPane("Timeline", TimelineView(id="gh-timeline"))
            yield TabPane("Issues", IssuesView(id="gh-issues"))
            yield TabPane("Plans", PlansView(id="gh-plans"))
            yield TabPane("PRs", PRsView(id="gh-prs"))

    async def on_mount(self) -> None:
        """Detect repo and load initial data."""
        if self._repo is None:
            try:
                if self._project_path:
                    self._repo = await detect_repo_from_path(
                        self._project_path
                    )
                else:
                    self._repo = await detect_repo_from_path(".")
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
        """Load data into all 4 views."""
        if self._repo is None:
            return

        timeline = self.query_one("#gh-timeline", TimelineView)
        plans = self.query_one("#gh-plans", PlansView)
        prs = self.query_one("#gh-prs", PRsView)

        await timeline.load(self._repo)
        await plans.load(self._repo)
        await prs.load(self._repo)

        # IssuesView fetches on mount via its own on_mount handler,
        # but we need to set the repo first
        issues = self.query_one("#gh-issues", IssuesView)
        issues._repo = self._repo
        await issues.fetch_and_render()

    async def refresh_data(self) -> None:
        """Re-fetch data for all views."""
        await self._load_all()

    async def action_refresh(self) -> None:
        """Handle the 'r' keybinding to refresh all GitHub data."""
        log.info("Refreshing GitHub data")
        await self._load_all()

    def _show_error(self, message: str) -> None:
        """Display an error message, hiding the tabbed content."""
        tabbed = self.query_one(TabbedContent)
        tabbed.display = False
        self.mount(Static(message, classes="gh-error"))
