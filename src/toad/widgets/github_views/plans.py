"""Plans view — plan issues with progress parsed from body checkboxes."""

from __future__ import annotations

import logging
import re
from typing import Any

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from toad.widgets.github_views.fetch import (
    GitHubFetchError,
    RepoInfo,
    fetch_issues,
    fetch_plan_issues,
)

log = logging.getLogger(__name__)

_CHECKBOX_CHECKED = re.compile(r"^\s*-\s*\[x\]", re.IGNORECASE | re.MULTILINE)
_CHECKBOX_ANY = re.compile(r"^\s*-\s*\[[ xX]\]", re.MULTILINE)


def parse_progress(body: str | None) -> tuple[int, int]:
    """Parse checked/total checkbox counts from an issue body.

    Returns (checked, total). Returns (0, 0) if no checkboxes found.
    """
    if not body:
        return 0, 0
    checked = len(_CHECKBOX_CHECKED.findall(body))
    total = len(_CHECKBOX_ANY.findall(body))
    return checked, total


def _progress_text(checked: int, total: int) -> str:
    if total == 0:
        return "no items"
    return f"{checked}/{total} done"


def _is_completed(issue: dict[str, Any]) -> bool:
    """Check if a plan issue is completed or closed."""
    if issue.get("state", "").upper() == "CLOSED":
        return True
    labels = {
        lb.get("name", "").lower()
        for lb in issue.get("labels", [])
    }
    return "plan:completed" in labels


def _label_names(issue: dict[str, Any]) -> str:
    labels = issue.get("labels", [])
    return ", ".join(lb.get("name", "") for lb in labels if lb.get("name"))


class PlansView(Static):
    """DataTable of plan issues with progress from body checkboxes."""

    DEFAULT_CSS = """
    PlansView {
        height: auto;
    }
    PlansView DataTable {
        height: auto;
        max-height: 20;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._show_closed = False

    def compose(self) -> ComposeResult:
        table = DataTable(id="plans-table", cursor_type="row", zebra_stripes=True)
        table.add_columns("#", "Title", "Status", "Progress", "Author")
        yield table

    async def load(self, repo: RepoInfo) -> None:
        """Fetch plan issues and populate the table."""
        table = self.query_one("#plans-table", DataTable)
        table.clear()

        try:
            all_issues = await fetch_plan_issues(repo)
            if not all_issues:
                all_open = await fetch_issues(repo, state="open")
                all_issues = [
                    i for i in all_open
                    if (i.get("title") or "").startswith("Plan:")
                ]
        except GitHubFetchError as exc:
            log.warning("Failed to fetch plan issues: %s", exc)
            table.add_row("--", str(exc), "", "", "")
            return

        if self._show_closed:
            visible = all_issues
        else:
            visible = [i for i in all_issues if not _is_completed(i)]

        if not visible:
            table.add_row("--", "No plan issues found", "", "", "")
            return

        for issue in visible:
            checked, total_cb = parse_progress(issue.get("body"))
            status = _label_names(issue)
            author = issue.get("author", {}).get("login", "")
            table.add_row(
                str(issue.get("number", "")),
                issue.get("title", ""),
                status,
                _progress_text(checked, total_cb),
                author,
            )

    def toggle_closed(self) -> None:
        """Toggle visibility of completed/closed plans."""
        self._show_closed = not self._show_closed
