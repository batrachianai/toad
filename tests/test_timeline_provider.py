"""Tests for TimelineProvider protocol and GitHubTimelineProvider.

Verifies:
- Protocol contract: GitHubTimelineProvider satisfies TimelineProvider
- Helper functions: _parse_date, _parse_priority, _parse_risk_labels,
  _normalize_status
- _build_board_map correctly extracts field values from GraphQL response
"""

from __future__ import annotations

from datetime import date

import pytest

from toad.widgets.github_views.github_timeline_provider import (
    GitHubTimelineProvider,
    _normalize_status,
    _parse_date,
    _parse_priority,
    _parse_risk_labels,
)
from toad.widgets.github_views.timeline_provider import (
    ItemStatus,
    Priority,
    TimelineProvider,
)


class TestProtocolConformance:
    """GitHubTimelineProvider must satisfy TimelineProvider protocol."""

    def test_isinstance_check(self) -> None:
        provider = GitHubTimelineProvider.__new__(GitHubTimelineProvider)
        assert isinstance(provider, TimelineProvider)

    def test_constructor_validates_repo_format(self) -> None:
        with pytest.raises(ValueError, match="owner/name"):
            GitHubTimelineProvider("bad-repo", project_number=1)

    def test_constructor_accepts_valid_repo(self) -> None:
        p = GitHubTimelineProvider("owner/repo", project_number=8)
        assert p._repo == "owner/repo"
        assert p._owner == "owner"
        assert p._project_number == 8


class TestParseDate:
    """_parse_date handles ISO dates and edge cases."""

    def test_valid_date(self) -> None:
        assert _parse_date("2026-04-03") == date(2026, 4, 3)

    def test_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_date("") is None

    def test_invalid_format_returns_none(self) -> None:
        assert _parse_date("not-a-date") is None


class TestParsePriority:
    """_parse_priority extracts p1-p4 from label lists."""

    def test_p1(self) -> None:
        assert _parse_priority(["p1", "other"]) == Priority.P1

    def test_p2_case_insensitive(self) -> None:
        assert _parse_priority(["P2"]) == Priority.P2

    def test_p3(self) -> None:
        assert _parse_priority(["p3"]) == Priority.P3

    def test_p4(self) -> None:
        assert _parse_priority(["p4"]) == Priority.P4

    def test_no_priority(self) -> None:
        assert _parse_priority(["bug", "feature"]) is None

    def test_empty_list(self) -> None:
        assert _parse_priority([]) is None

    def test_first_match_wins(self) -> None:
        assert _parse_priority(["p2", "p1"]) == Priority.P2


class TestParseRiskLabels:
    """_parse_risk_labels filters risk:* labels."""

    def test_extracts_risk_labels(self) -> None:
        result = _parse_risk_labels(["risk:dependency", "bug", "risk:api"])
        assert result == ["risk:dependency", "risk:api"]

    def test_no_risk_labels(self) -> None:
        assert _parse_risk_labels(["bug", "feature"]) == []

    def test_empty(self) -> None:
        assert _parse_risk_labels([]) == []

    def test_case_insensitive_prefix(self) -> None:
        result = _parse_risk_labels(["Risk:scope"])
        assert result == ["Risk:scope"]


class TestNormalizeStatus:
    """_normalize_status maps board Status values to ItemStatus."""

    def test_done(self) -> None:
        assert _normalize_status("Done") == ItemStatus.DONE

    def test_in_progress(self) -> None:
        assert _normalize_status("In Progress") == ItemStatus.IN_PROGRESS

    def test_in_progress_underscore(self) -> None:
        assert _normalize_status("in_progress") == ItemStatus.IN_PROGRESS

    def test_active(self) -> None:
        assert _normalize_status("active") == ItemStatus.IN_PROGRESS

    def test_todo(self) -> None:
        assert _normalize_status("Todo") == ItemStatus.TODO

    def test_unknown_defaults_to_todo(self) -> None:
        assert _normalize_status("backlog") == ItemStatus.TODO

    def test_none_defaults_to_todo(self) -> None:
        assert _normalize_status(None) == ItemStatus.TODO

    def test_empty_defaults_to_todo(self) -> None:
        assert _normalize_status("") == ItemStatus.TODO


class TestBuildBoardMap:
    """_build_board_map extracts issue field values from GraphQL data."""

    def test_extracts_fields(self) -> None:
        provider = GitHubTimelineProvider("o/r", project_number=1)
        data = {
            "data": {
                "organization": {
                    "projectV2": {
                        "items": {
                            "nodes": [
                                {
                                    "content": {"number": 42},
                                    "fieldValues": {
                                        "nodes": [
                                            {
                                                "field": {"name": "Status"},
                                                "name": "In Progress",
                                            },
                                            {
                                                "field": {
                                                    "name": "Start Date"
                                                },
                                                "date": "2026-04-01",
                                            },
                                            {
                                                "field": {
                                                    "name": "Target Date"
                                                },
                                                "date": "2026-04-15",
                                            },
                                            {
                                                "field": {"name": "Effort"},
                                                "number": 3,
                                            },
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                }
            }
        }
        result = provider._build_board_map(data)
        assert result[42]["Status"] == "In Progress"
        assert result[42]["Start Date"] == "2026-04-01"
        assert result[42]["Target Date"] == "2026-04-15"
        assert result[42]["Effort"] == "3"

    def test_skips_empty_nodes(self) -> None:
        provider = GitHubTimelineProvider("o/r", project_number=1)
        data = {
            "data": {
                "organization": {
                    "projectV2": {
                        "items": {
                            "nodes": [None, {"content": None}]
                        }
                    }
                }
            }
        }
        result = provider._build_board_map(data)
        assert result == {}

    def test_empty_project_data(self) -> None:
        provider = GitHubTimelineProvider("o/r", project_number=1)
        result = provider._build_board_map({})
        assert result == {}
