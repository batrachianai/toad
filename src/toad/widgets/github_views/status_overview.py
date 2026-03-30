"""Status overview — simple open plans and PRs summary."""

from __future__ import annotations

import logging
from typing import Any

from rich.text import Text
from textual.widgets import Static

from toad.widgets.github_views.fetch import (
    GitHubFetchError,
    RepoInfo,
    fetch_issues,
    fetch_plan_issues,
    fetch_prs,
)

log = logging.getLogger(__name__)


def _count_plans(
    labelled: list[dict[str, Any]],
    all_open: list[dict[str, Any]],
) -> int:
    """Count plans: labelled issues, or title-prefix fallback."""
    if labelled:
        return len(labelled)
    return sum(
        1 for i in all_open
        if (i.get("title") or "").startswith("Plan:")
    )


class StatusOverview(Static):
    """One-line summary of open plans and open PRs."""

    DEFAULT_CSS = """
    StatusOverview {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._repo: RepoInfo | None = None

    async def load(self, repo: RepoInfo) -> None:
        """Fetch counts and render summary."""
        self._repo = repo

        try:
            labelled_plans = await fetch_plan_issues(repo)
            all_open = await fetch_issues(repo, state="open")
            open_prs = await fetch_prs(repo, state="open")
        except GitHubFetchError as exc:
            log.warning("status overview fetch failed: %s", exc)
            self.update(
                Text(f"Fetch error: {exc}", style="italic red")
            )
            return

        plan_count = _count_plans(labelled_plans, all_open)
        pr_count = len(open_prs)

        summary = Text.assemble(
            ("Plans ", "bold"),
            (str(plan_count), "bold yellow"),
            ("  PRs ", "bold"),
            (str(pr_count), "bold cyan"),
        )
        self.update(summary)
