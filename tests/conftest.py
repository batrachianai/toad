"""Shared fixtures for Tasks-widget tests.

Provides mock ``gh`` CLI responses so ``TaskProvider`` tests stay offline
and deterministic.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import pytest

from toad.widgets.github_views.task_provider import TaskDetailData, TaskItem
from toad.widgets.github_views.timeline_provider import ItemStatus, Priority


@pytest.fixture
def mock_issues_payload() -> str:
    """Raw JSON string returned by ``gh issue list --json ...``."""
    issues: list[dict[str, Any]] = [
        {
            "number": 101,
            "title": "Wire Tasks tab",
            "state": "OPEN",
            "labels": [{"name": "p1"}, {"name": "risk:scope"}],
            "createdAt": "2026-04-10T12:00:00Z",
            "updatedAt": "2026-04-11T08:00:00Z",
            "milestone": {"number": 1, "title": "M1 — UI"},
            "url": "https://github.com/acme/proj/issues/101",
            "assignees": [{"login": "alberto"}],
            "comments": 4,
        },
        {
            "number": 102,
            "title": "Ship PM widget",
            "state": "CLOSED",
            "labels": [{"name": "p3"}],
            "createdAt": "2026-04-01T09:00:00Z",
            "updatedAt": "2026-04-12T10:00:00Z",
            "milestone": None,
            "url": "https://github.com/acme/proj/issues/102",
            "assignees": [],
            "comments": 0,
        },
    ]
    return json.dumps(issues)


@pytest.fixture
def mock_project_payload() -> str:
    """Raw JSON string returned by ``gh api graphql ...`` project query."""
    data = {
        "data": {
            "organization": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "content": {"number": 101},
                                "fieldValues": {
                                    "nodes": [
                                        {
                                            "field": {"name": "Status"},
                                            "name": "In Progress",
                                        },
                                        {
                                            "field": {"name": "Effort"},
                                            "number": 2,
                                        },
                                        {
                                            "field": {"name": "Start Date"},
                                            "date": "2026-04-10",
                                        },
                                        {
                                            "field": {"name": "Target Date"},
                                            "date": "2026-04-18",
                                        },
                                    ]
                                },
                            },
                            {
                                "content": {"number": 102},
                                "fieldValues": {"nodes": []},
                            },
                        ]
                    }
                }
            }
        }
    }
    return json.dumps(data)


@pytest.fixture
def mock_issue_detail_payload() -> str:
    """Raw JSON returned by ``gh issue view <n> --json ...``."""
    data = {
        "number": 101,
        "body": "## Heading\n\nBody text with **markdown**.",
        "comments": [
            {"author": {"login": "alice"}, "body": "+1"},
            {"author": {"login": "bob"}, "body": "LGTM"},
        ],
        "labels": [{"name": "p1"}, {"name": "risk:scope"}],
        "assignees": [{"login": "alberto"}],
        "url": "https://github.com/acme/proj/issues/101",
        "closedByPullRequestsReferences": [
            {"number": 200, "url": "https://github.com/acme/proj/pull/200"},
        ],
    }
    return json.dumps(data)


@pytest.fixture
def sample_tasks() -> list[TaskItem]:
    """Deterministic list of ``TaskItem`` for widget tests."""
    return [
        TaskItem(
            id="101",
            number=101,
            title="Wire Tasks tab",
            status=ItemStatus.IN_PROGRESS,
            milestone_id="1",
            milestone_title="M1 — UI",
            priority=Priority.P1,
            assignees=["alberto"],
            effort="2",
            labels=["p1", "risk:scope"],
            risk_labels=["risk:scope"],
            start_date=date(2026, 4, 10),
            target_date=date(2026, 4, 18),
            created_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc),
            comments_count=4,
            url="https://github.com/acme/proj/issues/101",
            state="open",
        ),
        TaskItem(
            id="102",
            number=102,
            title="Ship PM widget",
            status=ItemStatus.DONE,
            milestone_id=None,
            milestone_title="",
            priority=Priority.P3,
            assignees=[],
            effort=None,
            labels=["p3"],
            risk_labels=[],
            start_date=None,
            target_date=None,
            created_at=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
            comments_count=0,
            url="https://github.com/acme/proj/issues/102",
            state="closed",
        ),
    ]


@pytest.fixture
def sample_details() -> TaskDetailData:
    """Deterministic detail payload for a single task."""
    return TaskDetailData(
        number=101,
        body="## Heading\n\nBody text.",
        comments_count=2,
        linked_prs=[
            {"number": 200, "url": "https://github.com/acme/proj/pull/200"}
        ],
        labels=["p1", "risk:scope"],
        assignees=["alberto"],
        url="https://github.com/acme/proj/issues/101",
    )
