"""GitHubTimelineProvider — fetches timeline data from GitHub via gh CLI.

Implements the TimelineProvider protocol using milestones, issues, and
project board items from the GitHub API. All API calls go through the
existing _run_gh() subprocess wrapper in fetch.py.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from toad.widgets.github_views.fetch import _run_gh
from toad.widgets.github_views.timeline_provider import (
    ItemStatus,
    Priority,
    ProviderField,
    ProviderItem,
    ProviderMilestone,
    TimelineProvider,
)

log = logging.getLogger(__name__)

# GraphQL query for project board items with custom field values.
# Fetches up to 100 items with their field values in one call.
_PROJECT_ITEMS_QUERY = """
query($owner: String!, $number: Int!) {
  organization(login: $owner) {
    projectV2(number: $number) {
      fields(first: 30) {
        nodes {
          ... on ProjectV2Field {
            id
            name
            dataType
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            dataType
            options { id name }
          }
          ... on ProjectV2IterationField {
            id
            name
            dataType
          }
        }
      }
      items(first: 100) {
        nodes {
          content {
            ... on Issue {
              number
            }
          }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldTextValue {
                field { ... on ProjectV2Field { name } }
                text
              }
              ... on ProjectV2ItemFieldNumberValue {
                field { ... on ProjectV2Field { name } }
                number
              }
              ... on ProjectV2ItemFieldDateValue {
                field { ... on ProjectV2Field { name } }
                date
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2SingleSelectField { name } }
                name
              }
              ... on ProjectV2ItemFieldIterationValue {
                field { ... on ProjectV2IterationField { name } }
                title
              }
            }
          }
        }
      }
    }
  }
}
"""


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string (YYYY-MM-DD) into a date object."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        log.debug("unparseable date: %s", value)
        return None


def _parse_priority(labels: list[str]) -> Priority | None:
    """Extract priority from p1-p4 labels."""
    for label in labels:
        lower = label.lower()
        if lower == "p1":
            return Priority.P1
        if lower == "p2":
            return Priority.P2
        if lower == "p3":
            return Priority.P3
        if lower == "p4":
            return Priority.P4
    return None


def _parse_risk_labels(labels: list[str]) -> list[str]:
    """Extract risk:* labels."""
    return [lbl for lbl in labels if lbl.lower().startswith("risk:")]


def _normalize_status(status_text: str | None) -> ItemStatus:
    """Map a project board Status value to ItemStatus."""
    if not status_text:
        return ItemStatus.TODO
    lower = status_text.lower().strip()
    if lower == "done":
        return ItemStatus.DONE
    if lower in ("in progress", "in_progress", "active"):
        return ItemStatus.IN_PROGRESS
    return ItemStatus.TODO


class GitHubTimelineProvider:
    """TimelineProvider implementation backed by GitHub via gh CLI.

    Fetches milestones via ``gh api``, issues via ``gh issue list``,
    and project board items + fields via ``gh api graphql``.

    Args:
        repo: Owner/repo string (e.g. "DEGAorg/claude-code-config").
        project_number: GitHub Projects V2 board number.
    """

    def __init__(self, repo: str, project_number: int) -> None:
        if "/" not in repo:
            msg = f"repo must be owner/name, got: {repo!r}"
            raise ValueError(msg)
        self._repo = repo
        self._owner = repo.split("/", 1)[0]
        self._project_number = project_number
        self._cached_fields: list[ProviderField] | None = None

    async def fetch_milestones(self) -> list[ProviderMilestone]:
        """Fetch all milestones for the configured repo."""
        raw = await _run_gh(
            "api",
            f"repos/{self._repo}/milestones",
            "--paginate",
            "--jq",
            ".[] | {number, title, due_on, description}",
        )
        milestones: list[ProviderMilestone] = []
        for line in raw.strip().splitlines():
            if not line.strip():
                continue
            data: dict[str, Any] = json.loads(line)
            due = _parse_date(
                data.get("due_on", "")[:10]
                if data.get("due_on")
                else None
            )
            milestones.append(
                ProviderMilestone(
                    id=str(data["number"]),
                    title=data.get("title", ""),
                    due_date=due,
                    description=data.get("description", "") or "",
                )
            )
        return milestones

    async def fetch_items(self) -> list[ProviderItem]:
        """Fetch issues and enrich with project board field values."""
        issues_raw, project_data = await self._fetch_issues_and_project()
        board_map = self._build_board_map(project_data)

        items: list[ProviderItem] = []
        for issue in issues_raw:
            number = issue.get("number", 0)
            label_names = [
                lbl.get("name", "") for lbl in issue.get("labels", [])
            ]
            board = board_map.get(number, {})

            status = _normalize_status(board.get("Status"))
            # Fallback: if no board status, derive from issue state
            if not board.get("Status"):
                gh_state = issue.get("state", "").lower()
                if gh_state == "closed":
                    status = ItemStatus.DONE

            start_date = _parse_date(board.get("Start Date"))
            target_date = _parse_date(board.get("Target Date"))

            # Fallback: use issue createdAt for start if missing
            if start_date is None:
                created = issue.get("createdAt", "")
                if created:
                    start_date = _parse_date(created[:10])

            # Fallback: use milestone due date for target if missing
            milestone_data = issue.get("milestone")
            milestone_id: str | None = None
            if milestone_data:
                milestone_id = str(milestone_data.get("number", ""))
                if target_date is None and milestone_data.get("dueOn"):
                    target_date = _parse_date(
                        milestone_data["dueOn"][:10]
                    )

            items.append(
                ProviderItem(
                    id=str(number),
                    title=issue.get("title", ""),
                    status=status,
                    start_date=start_date,
                    target_date=target_date,
                    milestone_id=milestone_id,
                    labels=label_names,
                    is_gate="gate" in [lbl.lower() for lbl in label_names],
                    priority=_parse_priority(label_names),
                    risk_labels=_parse_risk_labels(label_names),
                    effort=board.get("Effort"),
                    url=issue.get("url", ""),
                )
            )
        return items

    async def fetch_fields(self) -> list[ProviderField]:
        """Fetch project board field metadata (cached per session)."""
        if self._cached_fields is not None:
            return self._cached_fields

        project_data = await self._fetch_project_data()
        project = (
            project_data.get("data", {})
            .get("organization", {})
            .get("projectV2", {})
        )
        raw_fields = (
            project.get("fields", {}).get("nodes", [])
        )
        fields: list[ProviderField] = []
        for f in raw_fields:
            if not f:
                continue
            options: list[str] = []
            if "options" in f:
                options = [
                    o.get("name", "") for o in f.get("options", [])
                ]
            fields.append(
                ProviderField(
                    id=f.get("id", ""),
                    name=f.get("name", ""),
                    field_type=f.get("dataType", ""),
                    options=options,
                )
            )
        self._cached_fields = fields
        return fields

    async def fetch_task_details(
        self, issue_number: int
    ) -> dict[str, Any]:
        """Fetch body, comments, labels, assignees, and linked PRs for an issue.

        Returns the raw ``gh issue view --json`` payload so callers can
        decide how to render it. Kept on the timeline provider so callers
        with a single provider handle can still drill into issue details.
        """
        raw = await _run_gh(
            "issue",
            "view",
            str(issue_number),
            "--repo",
            self._repo,
            "--json",
            "number,body,comments,labels,assignees,url,closedByPullRequestsReferences",
        )
        result: dict[str, Any] = json.loads(raw)
        return result

    async def _fetch_issues_and_project(
        self,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch issues and project data concurrently."""
        import asyncio

        issues_task = asyncio.create_task(self._fetch_issues())
        project_task = asyncio.create_task(self._fetch_project_data())
        issues, project = await asyncio.gather(issues_task, project_task)
        return issues, project

    async def _fetch_issues(self) -> list[dict[str, Any]]:
        """Fetch all issues (open + closed) from the repo."""
        raw = await _run_gh(
            "issue",
            "list",
            "--repo",
            self._repo,
            "--state",
            "all",
            "--json",
            "number,title,state,labels,createdAt,milestone,url",
            "--limit",
            "200",
        )
        result: list[dict[str, Any]] = json.loads(raw)
        return result

    async def _fetch_project_data(self) -> dict[str, Any]:
        """Fetch project board items and fields via GraphQL."""
        raw = await _run_gh(
            "api",
            "graphql",
            "-f",
            f"owner={self._owner}",
            "-F",
            f"number={self._project_number}",
            "-f",
            f"query={_PROJECT_ITEMS_QUERY}",
            timeout_s=30,
        )
        result: dict[str, Any] = json.loads(raw)
        return result

    def _build_board_map(
        self, project_data: dict[str, Any]
    ) -> dict[int, dict[str, str]]:
        """Build issue_number -> {field_name: value} from project data."""
        project = (
            project_data.get("data", {})
            .get("organization", {})
            .get("projectV2", {})
        )
        items = project.get("items", {}).get("nodes", [])
        board_map: dict[int, dict[str, str]] = {}

        for item in items:
            if not item:
                continue
            content = item.get("content")
            if not content or "number" not in content:
                continue
            number = content["number"]
            fields: dict[str, str] = {}
            for fv in item.get("fieldValues", {}).get("nodes", []):
                if not fv:
                    continue
                field_info = fv.get("field", {})
                field_name = field_info.get("name", "")
                if not field_name:
                    continue
                # Extract value from whichever type-specific key is present
                value = (
                    fv.get("text")
                    or fv.get("name")
                    or fv.get("title")
                    or fv.get("date")
                )
                if fv.get("number") is not None and value is None:
                    value = str(fv["number"])
                if value is not None:
                    fields[field_name] = str(value)
            board_map[number] = fields

        return board_map


# Runtime check that the class satisfies the protocol.
assert isinstance(
    GitHubTimelineProvider.__new__(GitHubTimelineProvider),
    TimelineProvider,
), "GitHubTimelineProvider does not satisfy TimelineProvider protocol"
