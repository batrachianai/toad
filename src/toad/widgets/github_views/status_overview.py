"""Status overview — colored count cards for plan states, issues, and PRs."""

from __future__ import annotations

import logging
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from toad.widgets.github_views.fetch import (
    PLAN_LABELS,
    GitHubFetchError,
    RepoInfo,
    fetch_all_plan_issues,
    fetch_issues,
    fetch_prs,
)

log = logging.getLogger(__name__)

# label -> (display name, Rich color)
_LABEL_STYLE: dict[str, tuple[str, str]] = {
    "plan:draft": ("Draft", "bright_black"),
    "plan:active": ("Active", "green"),
    "plan:pr-review": ("Review", "dodger_blue2"),
    "plan:completed": ("Done", "medium_purple"),
    "plan:failed": ("Failed", "red"),
}

_ISSUES_STYLE = ("Issues", "yellow")
_PRS_STYLE = ("PRs", "cyan")


def _count_by_label(
    issues: list[dict[str, Any]],
) -> dict[str, int]:
    """Count issues per plan:* label."""
    counts: dict[str, int] = {label: 0 for label in PLAN_LABELS}
    for issue in issues:
        for lbl in issue.get("labels") or []:
            name = lbl.get("name", "")
            if name in counts:
                counts[name] += 1
    return counts


def _render_card(count: int, name: str, color: str) -> Text:
    """Build a Rich Text card: count on top, label below, all colored."""
    return Text.assemble(
        (f" {count:>3} ", f"bold {color}"),
        "\n",
        (f" {name:<5} ", color),
    )


class StatusOverview(Static):
    """Horizontal row of colored status count cards."""

    DEFAULT_CSS = """
    StatusOverview {
        height: auto;
        padding: 0 1;
    }
    StatusOverview Horizontal {
        height: auto;
        align: left middle;
    }
    StatusOverview .status-card {
        width: auto;
        min-width: 9;
        height: 3;
        content-align: center middle;
        margin: 0 1 0 0;
        border: round $surface-lighten-2;
        padding: 0 1;
    }
    StatusOverview .status-error {
        color: $error;
        text-style: italic;
        padding: 1 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._repo: RepoInfo | None = None

    def compose(self) -> ComposeResult:
        yield Static("Loading status...", id="status-loading")

    async def load(self, repo: RepoInfo) -> None:
        """Fetch counts and render status cards."""
        self._repo = repo

        loading = self.query_one("#status-loading", Static)

        try:
            plan_issues = await fetch_all_plan_issues(repo)
        except GitHubFetchError as exc:
            log.warning("status overview fetch failed: %s", exc)
            loading.update(f"Fetch error: {exc}")
            loading.add_class("status-error")
            return

        label_counts = _count_by_label(plan_issues)

        try:
            all_open_issues = await fetch_issues(repo, state="open")
            all_open_prs = await fetch_prs(repo, state="open")
        except GitHubFetchError:
            all_open_issues = []
            all_open_prs = []

        await loading.remove()

        row = Horizontal()
        await self.mount(row)

        for label in PLAN_LABELS:
            name, color = _LABEL_STYLE[label]
            count = label_counts.get(label, 0)
            card = Static(
                _render_card(count, name, color),
                classes="status-card",
            )
            await row.mount(card)

        # Open issues card
        issues_name, issues_color = _ISSUES_STYLE
        issues_card = Static(
            _render_card(len(all_open_issues), issues_name, issues_color),
            classes="status-card",
        )
        await row.mount(issues_card)

        # Open PRs card
        prs_name, prs_color = _PRS_STYLE
        prs_card = Static(
            _render_card(len(all_open_prs), prs_name, prs_color),
            classes="status-card",
        )
        await row.mount(prs_card)
