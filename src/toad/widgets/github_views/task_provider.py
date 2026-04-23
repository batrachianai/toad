"""TaskProvider — fetches project-board tasks (issues) with rich metadata.

Kept separate from ``TimelineProvider`` so the timeline data path stays
stable. ``TaskItem`` is a richer superset of ``ProviderItem`` used by the
interactive Tasks widget (body, comments, linked PRs, assignees).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from toad.widgets.github_views.fetch import _run_gh
from toad.widgets.github_views.github_timeline_provider import (
    _PROJECT_ITEMS_QUERY,
    _normalize_status,
    _parse_date,
    _parse_priority,
    _parse_risk_labels,
)
from toad.widgets.github_views.timeline_provider import ItemStatus, Priority

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskItem:
    """A project-board item (issue or PR) with metadata for the Board widget.

    Superset of ``ProviderItem`` including fields only required by the
    interactive list and detail views. ``is_pr`` distinguishes PRs from
    issues; the PR-specific fields (``review_state``, ``ci_state``,
    ``mergeable``) are ``None`` for plain issues.
    """

    id: str
    number: int
    title: str
    status: ItemStatus
    milestone_id: str | None = None
    milestone_title: str = ""
    priority: Priority | None = None
    assignees: list[str] = field(default_factory=list)
    effort: str | None = None
    labels: list[str] = field(default_factory=list)
    risk_labels: list[str] = field(default_factory=list)
    start_date: date | None = None
    target_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    comments_count: int = 0
    url: str = ""
    state: str = "open"
    # PR-only fields (populated when is_pr=True, else None)
    is_pr: bool = False
    review_state: str | None = None  # APPROVED / CHANGES_REQUESTED / REVIEW_REQUIRED / COMMENTED
    ci_state: str | None = None  # SUCCESS / FAILURE / PENDING / NONE
    mergeable: str | None = None  # MERGEABLE / CONFLICTING / UNKNOWN
    author: str | None = None
    # Plan-only field (populated when labels contain "type:plan")
    progress_pct: int | None = None  # 0..100, or None when no checklist found


@dataclass(frozen=True)
class TaskDetailData:
    """Lazy-loaded detail payload for a single task."""

    number: int
    body: str = ""
    comments_count: int = 0
    linked_prs: list[dict[str, Any]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    url: str = ""


def _comments_count(value: Any) -> int:
    """Parse a ``comments`` field which may be an int or a list of comment dicts.

    ``gh issue list --json comments`` returns the full comment list; older
    call sites return an integer count. Handle both defensively.
    """
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime (with trailing Z) into a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        log.debug("unparseable datetime: %s", value)
        return None


# Markdown checkbox regex — matches `- [ ]` / `- [x]` / `* [X]` / `+ [ ]`.
_CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]", re.MULTILINE)


def _progress_from_body(body: str) -> int | None:
    """Return % of checked boxes in ``body``, or ``None`` if no checklist."""
    if not body:
        return None
    matches = _CHECKBOX_RE.findall(body)
    if not matches:
        return None
    checked = sum(1 for m in matches if m.lower() == "x")
    return round(100 * checked / len(matches))


def _pr_to_task_item(pr: dict[str, Any]) -> TaskItem:
    """Convert a ``gh pr list --json`` entry to a TaskItem with PR fields."""
    number = int(pr.get("number", 0))
    labels = [lbl.get("name", "") for lbl in pr.get("labels", [])]
    state_raw = str(pr.get("state", "open")).lower()
    status = ItemStatus.IN_PROGRESS if state_raw == "open" else ItemStatus.DONE
    if pr.get("isDraft"):
        status = ItemStatus.TODO
    milestone_data = pr.get("milestone") or {}
    milestone_id = (
        str(milestone_data.get("number"))
        if milestone_data.get("number") is not None
        else None
    )
    assignees = [
        a.get("login", "") for a in (pr.get("assignees") or []) if a
    ]
    author = (pr.get("author") or {}).get("login") or None
    rollup = pr.get("statusCheckRollup") or []
    ci_state = _summarize_ci(rollup)
    return TaskItem(
        id=f"pr-{number}",
        number=number,
        title=pr.get("title", ""),
        status=status,
        milestone_id=milestone_id,
        milestone_title=milestone_data.get("title", "") or "",
        priority=_parse_priority(labels),
        assignees=assignees,
        labels=labels,
        risk_labels=_parse_risk_labels(labels),
        created_at=_parse_datetime(pr.get("createdAt")),
        updated_at=_parse_datetime(pr.get("updatedAt")),
        url=pr.get("url", ""),
        state=state_raw,
        is_pr=True,
        review_state=pr.get("reviewDecision") or "REVIEW_REQUIRED",
        ci_state=ci_state,
        mergeable=pr.get("mergeable"),
        author=author,
    )


def _summarize_ci(rollup: list[dict[str, Any]]) -> str:
    """Collapse a statusCheckRollup list to one of SUCCESS / FAILURE / PENDING / NONE."""
    if not rollup:
        return "NONE"
    states: set[str] = set()
    for entry in rollup:
        state = (
            entry.get("state")
            or entry.get("conclusion")
            or entry.get("status")
            or ""
        ).upper()
        if state:
            states.add(state)
    if "FAILURE" in states or "ERROR" in states:
        return "FAILURE"
    if "PENDING" in states or "IN_PROGRESS" in states or "QUEUED" in states:
        return "PENDING"
    if states and all(s in {"SUCCESS", "COMPLETED"} for s in states):
        return "SUCCESS"
    return "NONE"


@runtime_checkable
class TaskProviderProtocol(Protocol):
    """Minimal protocol implemented by ``TaskProvider``."""

    async def fetch_tasks(self) -> list[TaskItem]: ...

    async def fetch_task_details(self, issue_number: int) -> TaskDetailData: ...


class TaskProvider:
    """Fetches project-board tasks from GitHub via ``gh`` CLI.

    Args:
        repo: Owner/repo string (e.g. ``"DEGAorg/claude-code-config"``).
        project_number: GitHub Projects V2 board number.
    """

    def __init__(self, repo: str, project_number: int) -> None:
        if "/" not in repo:
            msg = f"repo must be owner/name, got: {repo!r}"
            raise ValueError(msg)
        self._repo = repo
        self._owner = repo.split("/", 1)[0]
        self._project_number = project_number

    async def fetch_tasks(self) -> list[TaskItem]:
        """Fetch issues + PRs from the repo, enriched with board fields."""
        issues_task = asyncio.create_task(self._fetch_issues())
        project_task = asyncio.create_task(self._fetch_project_data())
        prs_task = asyncio.create_task(self._fetch_prs())
        issues, project, prs = await asyncio.gather(
            issues_task, project_task, prs_task
        )
        board_map = _build_board_map(project)

        tasks: list[TaskItem] = []
        for issue in issues:
            number = issue.get("number", 0)
            labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
            board = board_map.get(number, {})

            status = _normalize_status(board.get("Status"))
            if not board.get("Status") and issue.get("state", "").lower() == "closed":
                status = ItemStatus.DONE

            milestone_data = issue.get("milestone") or {}
            milestone_id = (
                str(milestone_data.get("number"))
                if milestone_data.get("number") is not None
                else None
            )
            milestone_title = milestone_data.get("title", "") or ""

            assignees = [
                a.get("login", "") for a in issue.get("assignees", []) if a
            ]

            # Plan progress = ratio of checked markdown boxes in body.
            progress_pct: int | None = None
            if any(lbl.lower() == "type:plan" for lbl in labels):
                progress_pct = _progress_from_body(issue.get("body", ""))

            tasks.append(
                TaskItem(
                    id=str(number),
                    number=number,
                    title=issue.get("title", ""),
                    status=status,
                    milestone_id=milestone_id,
                    milestone_title=milestone_title,
                    priority=_parse_priority(labels),
                    assignees=assignees,
                    effort=board.get("Effort"),
                    labels=labels,
                    risk_labels=_parse_risk_labels(labels),
                    start_date=_parse_date(board.get("Start Date")),
                    target_date=_parse_date(board.get("Target Date")),
                    created_at=_parse_datetime(issue.get("createdAt")),
                    updated_at=_parse_datetime(issue.get("updatedAt")),
                    comments_count=_comments_count(issue.get("comments")),
                    url=issue.get("url", ""),
                    state=issue.get("state", "open").lower(),
                    progress_pct=progress_pct,
                )
            )
        for pr in prs:
            tasks.append(_pr_to_task_item(pr))
        return tasks

    async def fetch_task_details(self, issue_number: int) -> TaskDetailData:
        """Fetch body, comments, and linked PRs for a single issue."""
        raw = await _run_gh(
            "issue",
            "view",
            str(issue_number),
            "--repo",
            self._repo,
            "--json",
            "number,body,comments,labels,assignees,url,closedByPullRequestsReferences",
        )
        data: dict[str, Any] = json.loads(raw)
        comments = data.get("comments") or []
        linked = data.get("closedByPullRequestsReferences") or []
        return TaskDetailData(
            number=int(data.get("number", issue_number)),
            body=data.get("body", "") or "",
            comments_count=len(comments),
            linked_prs=list(linked),
            labels=[lbl.get("name", "") for lbl in data.get("labels", [])],
            assignees=[
                a.get("login", "") for a in data.get("assignees", []) if a
            ],
            url=data.get("url", ""),
        )

    async def _fetch_issues(self) -> list[dict[str, Any]]:
        raw = await _run_gh(
            "issue",
            "list",
            "--repo",
            self._repo,
            "--state",
            "all",
            "--json",
            "number,title,state,labels,body,createdAt,updatedAt,milestone,url,assignees,comments",
            "--limit",
            "200",
        )
        result: list[dict[str, Any]] = json.loads(raw)
        return result

    async def _fetch_prs(self) -> list[dict[str, Any]]:
        """Fetch open + recently-merged PRs. Used to populate the PRs chip.

        Returns an empty list if the call fails (never blocks issue fetch).
        """
        try:
            raw = await _run_gh(
                "pr",
                "list",
                "--repo",
                self._repo,
                "--state",
                "all",
                "--json",
                "number,title,state,labels,createdAt,updatedAt,url,author,"
                "reviewDecision,statusCheckRollup,mergeable,isDraft,milestone,assignees",
                "--limit",
                "100",
            )
            result: list[dict[str, Any]] = json.loads(raw)
            return result
        except Exception as exc:
            log.warning("Failed to fetch PRs: %s", exc)
            return []

    async def _fetch_project_data(self) -> dict[str, Any]:
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
    project_data: dict[str, Any],
) -> dict[int, dict[str, str]]:
    """Flatten GraphQL project data to issue_number -> {field: value}."""
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
            field_name = (fv.get("field") or {}).get("name", "")
            if not field_name:
                continue
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


assert isinstance(
    TaskProvider.__new__(TaskProvider), TaskProviderProtocol
), "TaskProvider does not satisfy TaskProviderProtocol"
