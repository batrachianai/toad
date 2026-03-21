"""Tests for the GitHub panel PM dashboard redesign.

Verifies:
- StatusOverview renders correct count cards for each plan state
- TimelineView displays plan events sorted by recency with colored badges
- GitHubStateWidget composes the PM dashboard layout with collapsible detail tabs
- Helper functions (_count_by_label, _plan_label, _relative_time) work correctly
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
from rich.text import Text

from toad.widgets.github_views.fetch import PLAN_LABELS, RepoInfo
from toad.widgets.github_views.status_overview import (
    StatusOverview,
    _count_by_label,
    _render_card,
)
from toad.widgets.github_views.timeline import (
    LABEL_COLORS,
    TimelineView,
    _label_badge,
    _plan_label,
    _relative_time,
)


FAKE_REPO = RepoInfo(owner="DEGAorg", repo="claude-code-config")


def _make_issue(
    number: int,
    title: str,
    labels: list[str],
    updated_at: str = "2026-03-20T12:00:00Z",
) -> dict[str, Any]:
    """Build a fake issue dict matching gh CLI JSON output."""
    return {
        "number": number,
        "title": title,
        "labels": [{"name": lbl} for lbl in labels],
        "state": "OPEN",
        "updatedAt": updated_at,
        "createdAt": updated_at,
        "author": {"login": "test-user"},
    }


SAMPLE_ISSUES = [
    _make_issue(1, "Setup infra", ["plan:active"]),
    _make_issue(2, "Auth module", ["plan:active"]),
    _make_issue(3, "Deploy pipeline", ["plan:completed"]),
    _make_issue(4, "Fix flaky test", ["plan:pr-review"]),
    _make_issue(5, "Broken build", ["plan:failed"]),
    _make_issue(6, "Draft idea", ["plan:draft"]),
    _make_issue(7, "Another draft", ["plan:draft"]),
]


class TestCountByLabel:
    """_count_by_label correctly tallies issues per plan:* label."""

    def test_counts_each_label(self):
        counts = _count_by_label(SAMPLE_ISSUES)
        assert counts["plan:active"] == 2
        assert counts["plan:completed"] == 1
        assert counts["plan:pr-review"] == 1
        assert counts["plan:failed"] == 1
        assert counts["plan:draft"] == 2

    def test_empty_issues(self):
        counts = _count_by_label([])
        for label in PLAN_LABELS:
            assert counts[label] == 0

    def test_issue_with_no_plan_label(self):
        issues = [_make_issue(10, "Bug report", ["bug"])]
        counts = _count_by_label(issues)
        for label in PLAN_LABELS:
            assert counts[label] == 0

    def test_issue_with_multiple_plan_labels(self):
        issues = [
            _make_issue(
                11, "Dual label", ["plan:active", "plan:pr-review"]
            )
        ]
        counts = _count_by_label(issues)
        assert counts["plan:active"] == 1
        assert counts["plan:pr-review"] == 1

    def test_missing_labels_key(self):
        issues = [{"number": 99, "title": "No labels"}]
        counts = _count_by_label(issues)
        for label in PLAN_LABELS:
            assert counts[label] == 0


class TestRenderCard:
    """_render_card produces Rich Text with count and label."""

    def test_card_contains_count(self):
        card = _render_card(5, "Active", "green")
        assert isinstance(card, Text)
        assert "5" in card.plain

    def test_card_contains_name(self):
        card = _render_card(0, "Draft", "bright_black")
        assert "Draft" in card.plain

    def test_card_zero_count(self):
        card = _render_card(0, "Failed", "red")
        assert "0" in card.plain


class TestPlanLabel:
    """_plan_label extracts the first plan:* label from an issue."""

    def test_extracts_plan_label(self):
        issue = _make_issue(1, "Test", ["bug", "plan:active"])
        assert _plan_label(issue) == "plan:active"

    def test_returns_none_when_no_plan_label(self):
        issue = _make_issue(2, "Test", ["bug", "enhancement"])
        assert _plan_label(issue) is None

    def test_returns_first_plan_label(self):
        issue = _make_issue(
            3, "Test", ["plan:active", "plan:pr-review"]
        )
        assert _plan_label(issue) == "plan:active"

    def test_empty_labels(self):
        issue = _make_issue(4, "Test", [])
        assert _plan_label(issue) is None


class TestLabelBadge:
    """_label_badge produces colored Rich Text."""

    def test_known_label_has_color(self):
        badge = _label_badge("plan:active")
        assert isinstance(badge, Text)
        assert badge.plain == "plan:active"
        assert badge.style == LABEL_COLORS["plan:active"]

    def test_unknown_label_uses_white(self):
        badge = _label_badge("plan:unknown")
        assert badge.style == "white"

    def test_all_known_labels_have_colors(self):
        for label in PLAN_LABELS:
            badge = _label_badge(label)
            assert badge.style == LABEL_COLORS[label]


class TestRelativeTime:
    """_relative_time converts ISO timestamps to human-friendly strings."""

    def test_recent_is_just_now(self):
        now = datetime.now(tz=timezone.utc).isoformat()
        assert _relative_time(now) == "just now"

    def test_invalid_timestamp_returns_truncated(self):
        assert _relative_time("not-a-date") == "not-a-date"

    def test_empty_string(self):
        assert _relative_time("") == "?"

    def test_old_date_shows_days(self):
        result = _relative_time("2020-01-01T00:00:00Z")
        assert result.endswith("d ago")


class TestStatusOverviewWidget:
    """StatusOverview widget structure and composition."""

    def test_is_static_subclass(self):
        assert issubclass(StatusOverview, __import__(
            "textual.widgets", fromlist=["Static"]
        ).Static)

    def test_has_load_method(self):
        assert callable(getattr(StatusOverview, "load", None))

    def test_default_css_has_card_class(self):
        assert ".status-card" in StatusOverview.DEFAULT_CSS


class TestTimelineViewWidget:
    """TimelineView widget structure and composition."""

    def test_has_load_method(self):
        assert callable(getattr(TimelineView, "load", None))

    def test_label_colors_cover_all_plan_labels(self):
        for label in PLAN_LABELS:
            assert label in LABEL_COLORS, (
                f"{label} missing from LABEL_COLORS"
            )

    def test_default_css_has_error_class(self):
        assert ".error-label" in TimelineView.DEFAULT_CSS


class TestGitHubStateWidgetComposition:
    """GitHubStateWidget uses PM dashboard layout."""

    def test_imports_status_overview(self):
        from toad.widgets.github_state import StatusOverview as SO

        assert SO is StatusOverview

    def test_imports_timeline_view(self):
        from toad.widgets.github_state import TimelineView as TV

        assert TV is TimelineView

    def test_has_refresh_binding(self):
        from toad.widgets.github_state import GitHubStateWidget

        keys = [b.key for b in GitHubStateWidget.BINDINGS]
        assert "r" in keys

    def test_css_has_collapsible_style(self):
        from toad.widgets.github_state import GitHubStateWidget

        assert "Collapsible" in GitHubStateWidget.DEFAULT_CSS

    def test_css_has_tabbed_content_style(self):
        from toad.widgets.github_state import GitHubStateWidget

        assert "TabbedContent" in GitHubStateWidget.DEFAULT_CSS

    def test_compose_yields_correct_structure(self):
        """Verify compose uses StatusOverview, TimelineView, and
        Collapsible with TabbedContent."""
        import inspect

        from toad.widgets.github_state import GitHubStateWidget

        source = inspect.getsource(GitHubStateWidget.compose)
        assert "StatusOverview" in source
        assert "TimelineView" in source
        assert "Collapsible" in source
        assert "collapsed=True" in source
        assert "TabbedContent" in source
        assert "IssuesView" in source
        assert "PlansView" in source
        assert "PRsView" in source


class TestFetchAllPlanIssues:
    """fetch_all_plan_issues fetches across all plan:* labels."""

    def test_plan_labels_has_five_entries(self):
        assert len(PLAN_LABELS) == 5
        assert "plan:draft" in PLAN_LABELS
        assert "plan:active" in PLAN_LABELS
        assert "plan:pr-review" in PLAN_LABELS
        assert "plan:completed" in PLAN_LABELS
        assert "plan:failed" in PLAN_LABELS

    def test_fetch_all_plan_issues_exists(self):
        from toad.widgets.github_views.fetch import fetch_all_plan_issues

        assert callable(fetch_all_plan_issues)

    @pytest.mark.asyncio
    async def test_fetch_all_deduplicates_by_number(self):
        """Issues appearing under multiple labels are deduplicated."""
        from toad.widgets.github_views.fetch import fetch_all_plan_issues

        # Issue 1 appears under both plan:active and plan:pr-review
        label_results = {
            "plan:draft": [],
            "plan:active": [
                _make_issue(1, "Dup", ["plan:active"]),
            ],
            "plan:pr-review": [
                _make_issue(1, "Dup", ["plan:pr-review"]),
            ],
            "plan:completed": [],
            "plan:failed": [],
        }

        call_count = 0

        async def mock_run_gh(*args: str, timeout_s: float = 15) -> str:
            nonlocal call_count
            import json

            # Parse which label is being queried
            for i, arg in enumerate(args):
                if arg == "--label" and i + 1 < len(args):
                    label = args[i + 1]
                    call_count += 1
                    return json.dumps(label_results.get(label, []))
            return "[]"

        with patch(
            "toad.widgets.github_views.fetch._run_gh",
            side_effect=mock_run_gh,
        ):
            result = await fetch_all_plan_issues(FAKE_REPO)

        # Deduplicated: only 1 issue despite appearing twice
        assert len(result) == 1
        assert result[0]["number"] == 1
        # Called once per label
        assert call_count == 5
