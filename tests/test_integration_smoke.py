"""Integration smoke test — verify timeline renders from live GitHub data.

Requires ``gh`` CLI authenticated with access to ``DEGAorg/claude-code-config``
and project board #8.  Skip automatically when gh is not available or not
authenticated (CI-friendly).
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest

from toad.widgets.gantt_timeline import render_gantt
from toad.widgets.github_views.github_timeline_provider import (
    GitHubTimelineProvider,
)
from toad.widgets.github_views.timeline_data import (
    TimelineData,
    build_timeline,
)
from toad.widgets.github_views.timeline_provider import ItemStatus


def _gh_is_authenticated() -> bool:
    """Return True if ``gh`` is installed and authenticated."""
    gh = shutil.which("gh")
    if not gh:
        return False
    try:
        result = subprocess.run(
            [gh, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gh_is_authenticated(),
    reason="gh CLI not authenticated — skip live integration tests",
)

REPO = "DEGAorg/claude-code-config"
PROJECT_NUMBER = 8


@pytest.fixture
def provider() -> GitHubTimelineProvider:
    return GitHubTimelineProvider(repo=REPO, project_number=PROJECT_NUMBER)


class TestLiveProvider:
    """Fetch real data from GitHub and verify structure."""

    def test_fetch_milestones(
        self, provider: GitHubTimelineProvider
    ) -> None:
        milestones = asyncio.run(provider.fetch_milestones())
        assert isinstance(milestones, list)
        # Repo should have at least one milestone
        assert len(milestones) > 0, "Expected at least one milestone"
        ms = milestones[0]
        assert ms.id
        assert ms.title

    def test_fetch_items(
        self, provider: GitHubTimelineProvider
    ) -> None:
        items = asyncio.run(provider.fetch_items())
        assert isinstance(items, list)
        assert len(items) > 0, "Expected at least one issue"
        item = items[0]
        assert item.id
        assert item.title
        assert isinstance(item.status, ItemStatus)

    def test_fetch_fields(
        self, provider: GitHubTimelineProvider
    ) -> None:
        fields = asyncio.run(provider.fetch_fields())
        assert isinstance(fields, list)
        assert len(fields) > 0, "Expected project board fields"
        field_names = {f.name for f in fields}
        # Project board #8 should have these standard fields
        assert "Status" in field_names, (
            f"Missing 'Status' field; got {field_names}"
        )


class TestLivePipeline:
    """Full provider → transform → render pipeline with live data."""

    def test_build_timeline_from_live_data(
        self, provider: GitHubTimelineProvider
    ) -> None:
        milestones = asyncio.run(provider.fetch_milestones())
        items = asyncio.run(provider.fetch_items())
        timeline = build_timeline(milestones, items)

        assert isinstance(timeline, TimelineData)
        assert timeline.total_days >= 1
        assert len(timeline.groups) > 0, "Expected at least one group"

        # Verify items are present
        total_items = sum(
            len(g.items) for g in timeline.groups
        )
        assert total_items > 0, "Expected items in groups"

    def test_render_gantt_from_live_data(
        self, provider: GitHubTimelineProvider
    ) -> None:
        milestones = asyncio.run(provider.fetch_milestones())
        items = asyncio.run(provider.fetch_items())
        timeline = build_timeline(milestones, items)
        lines = render_gantt(timeline, track_width=80)

        assert len(lines) > 0, "Gantt should produce output lines"
        # At least: date axis (2) + separator (1) + 1 group header + 1 bar
        assert len(lines) >= 4, (
            f"Expected >= 4 lines, got {len(lines)}"
        )

        # Verify we have text content (not empty)
        text_content = "\n".join(str(line) for line in lines)
        assert len(text_content) > 100, "Gantt output seems too short"

    def test_status_colors_present(
        self, provider: GitHubTimelineProvider
    ) -> None:
        """Verify that at least one status type is rendered."""
        items = asyncio.run(provider.fetch_items())
        statuses = {item.status for item in items}
        # The repo should have items in at least one status
        assert len(statuses) > 0, "Expected at least one status"
        assert statuses.issubset(
            {ItemStatus.TODO, ItemStatus.IN_PROGRESS, ItemStatus.DONE}
        )

    def test_milestone_grouping(
        self, provider: GitHubTimelineProvider
    ) -> None:
        """Verify items are grouped by milestone."""
        milestones = asyncio.run(provider.fetch_milestones())
        items = asyncio.run(provider.fetch_items())
        timeline = build_timeline(milestones, items)

        group_titles = [g.title for g in timeline.groups]
        milestone_titles = {m.title for m in milestones}
        # At least one milestone group should match a real milestone
        matched = [
            t for t in group_titles if t in milestone_titles
        ]
        assert len(matched) > 0, (
            f"No milestone groups matched. "
            f"Groups: {group_titles}, Milestones: {milestone_titles}"
        )
