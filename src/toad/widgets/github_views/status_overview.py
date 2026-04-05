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


class StatusOverview(Static):
    """One-line summary of plans (total/completed/pending) and open PRs."""

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
            all_plans = await fetch_plan_issues(repo)
            if not all_plans:
                all_open = await fetch_issues(repo, state="open")
                all_plans = [
                    i for i in all_open
                    if (i.get("title") or "").startswith("Plan:")
                ]
            open_prs = await fetch_prs(repo, state="open")
        except GitHubFetchError as exc:
            log.warning("status overview fetch failed: %s", exc)
            self.update(
                Text(f"Fetch error: {exc}", style="italic red")
            )
            return

        active = 0
        pending = 0
        completed = 0
        for issue in all_plans:
            labels = {
                lb.get("name", "").lower()
                for lb in issue.get("labels", [])
            }
            is_closed = issue.get("state", "").upper() == "CLOSED"
            if is_closed or "plan:completed" in labels:
                completed += 1
            elif "plan:active" in labels or "plan:pr-review" in labels:
                active += 1
            else:
                pending += 1

        pr_count = len(open_prs)

        summary = Text.assemble(
            ("Active Plans ", "bold"),
            (str(active), "bold green"),
            (" | ", "dim"),
            ("Pending Plans ", "bold"),
            (str(pending), "bold yellow"),
            (" | ", "dim"),
            ("Completed Plans ", "bold"),
            (str(completed), "bold dim"),
            (" | ", "dim"),
            ("PRs ", "bold"),
            (str(pr_count), "bold cyan"),
        )
        self.update(summary)
