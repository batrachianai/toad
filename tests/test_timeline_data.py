"""Tests for timeline data transform layer.

Verifies:
- build_timeline groups items by milestone
- Date fallback logic (missing start/target dates)
- Gate markers extracted from gate items
- Ungrouped items placed in "Ungrouped" group
- Empty input returns sensible defaults
- Global date axis computed from all items and milestone due dates
"""

from __future__ import annotations

from datetime import date

from toad.widgets.github_views.timeline_data import (
    build_timeline,
)
from toad.widgets.github_views.timeline_provider import (
    ItemStatus,
    Priority,
    ProviderItem,
    ProviderMilestone,
)


TODAY = date(2026, 4, 3)


def _ms(
    id: str, title: str, due_date: date | None = None
) -> ProviderMilestone:
    return ProviderMilestone(id=id, title=title, due_date=due_date)


def _item(
    id: str = "1",
    title: str = "Task",
    status: ItemStatus = ItemStatus.TODO,
    start_date: date | None = None,
    target_date: date | None = None,
    milestone_id: str | None = None,
    is_gate: bool = False,
    priority: Priority | None = None,
    risk_labels: list[str] | None = None,
) -> ProviderItem:
    return ProviderItem(
        id=id,
        title=title,
        status=status,
        start_date=start_date,
        target_date=target_date,
        milestone_id=milestone_id,
        is_gate=is_gate,
        priority=priority,
        risk_labels=risk_labels or [],
    )


class TestBuildTimelineEmpty:
    """build_timeline with no items returns minimal TimelineData."""

    def test_empty_items(self) -> None:
        result = build_timeline([], [], today=TODAY)
        assert result.start_date == TODAY
        assert result.total_days == 1
        assert result.groups == []
        assert result.gates == []


class TestBuildTimelineGrouping:
    """Items are grouped by milestone; ungrouped items get a fallback group."""

    def test_groups_by_milestone(self) -> None:
        ms = [_ms("1", "Sprint 1")]
        items = [
            _item("10", "A", start_date=TODAY, milestone_id="1"),
            _item("11", "B", start_date=TODAY, milestone_id="1"),
        ]
        result = build_timeline(ms, items, today=TODAY)
        assert len(result.groups) == 1
        assert result.groups[0].title == "Sprint 1"
        assert len(result.groups[0].items) == 2

    def test_ungrouped_items(self) -> None:
        ms = [_ms("1", "Sprint 1")]
        items = [
            _item("10", "In Sprint", start_date=TODAY, milestone_id="1"),
            _item("20", "Orphan", start_date=TODAY, milestone_id=None),
        ]
        result = build_timeline(ms, items, today=TODAY)
        assert len(result.groups) == 2
        assert result.groups[0].title == "Sprint 1"
        assert result.groups[1].title == "Ungrouped"
        assert result.groups[1].items[0].title == "Orphan"

    def test_milestone_order_preserved(self) -> None:
        ms = [_ms("2", "Beta"), _ms("1", "Alpha")]
        items = [
            _item("10", "A", start_date=TODAY, milestone_id="2"),
            _item("11", "B", start_date=TODAY, milestone_id="1"),
        ]
        result = build_timeline(ms, items, today=TODAY)
        assert result.groups[0].title == "Beta"
        assert result.groups[1].title == "Alpha"


class TestDateFallbacks:
    """Missing dates resolved via fallback chain."""

    def test_missing_start_uses_today(self) -> None:
        items = [_item("1", "No start", start_date=None)]
        result = build_timeline([], items, today=TODAY)
        assert result.groups[0].items[0].start_day == 0
        assert result.start_date == TODAY

    def test_missing_target_uses_milestone_due(self) -> None:
        due = date(2026, 4, 10)
        ms = [_ms("1", "Sprint", due_date=due)]
        items = [
            _item(
                "1",
                "No target",
                start_date=TODAY,
                target_date=None,
                milestone_id="1",
            )
        ]
        result = build_timeline(ms, items, today=TODAY)
        item = result.groups[0].items[0]
        assert item.days == (due - TODAY).days

    def test_missing_target_no_milestone_uses_start(self) -> None:
        items = [
            _item("1", "Bare", start_date=TODAY, target_date=None)
        ]
        result = build_timeline([], items, today=TODAY)
        # target == start → duration clamped to 1
        assert result.groups[0].items[0].days == 1

    def test_target_before_start_clamped(self) -> None:
        items = [
            _item(
                "1",
                "Backwards",
                start_date=date(2026, 4, 5),
                target_date=date(2026, 4, 2),
            )
        ]
        result = build_timeline([], items, today=TODAY)
        item = result.groups[0].items[0]
        # target clamped to start, duration = 1
        assert item.days == 1


class TestGateMarkers:
    """Gate items produce GateMarker entries on the date axis."""

    def test_gate_item_creates_marker(self) -> None:
        items = [
            _item(
                "1", "Release Gate", start_date=TODAY, is_gate=True
            )
        ]
        result = build_timeline([], items, today=TODAY)
        assert len(result.gates) == 1
        assert result.gates[0].label == "Release Gate"
        assert result.gates[0].day == 0

    def test_gates_sorted_by_day(self) -> None:
        items = [
            _item(
                "1",
                "Late",
                start_date=date(2026, 4, 10),
                is_gate=True,
            ),
            _item(
                "2",
                "Early",
                start_date=date(2026, 4, 1),
                is_gate=True,
            ),
        ]
        result = build_timeline([], items, today=TODAY)
        assert result.gates[0].label == "Early"
        assert result.gates[1].label == "Late"

    def test_non_gate_no_marker(self) -> None:
        items = [
            _item("1", "Normal", start_date=TODAY, is_gate=False)
        ]
        result = build_timeline([], items, today=TODAY)
        assert result.gates == []


class TestDateAxis:
    """Global date axis spans all items and milestone due dates."""

    def test_axis_includes_milestone_due(self) -> None:
        due = date(2026, 5, 1)
        ms = [_ms("1", "Sprint", due_date=due)]
        items = [
            _item("1", "T", start_date=TODAY, milestone_id="1")
        ]
        result = build_timeline(ms, items, today=TODAY)
        # total_days should span at least from TODAY to due
        assert result.total_days >= (due - TODAY).days

    def test_axis_minimum_one_day(self) -> None:
        items = [_item("1", "Same day", start_date=TODAY)]
        result = build_timeline([], items, today=TODAY)
        assert result.total_days >= 1


class TestTimelineItemFields:
    """TimelineItem preserves provider fields through transform."""

    def test_fields_carried_through(self) -> None:
        items = [
            _item(
                "42",
                "Important",
                status=ItemStatus.IN_PROGRESS,
                start_date=TODAY,
                target_date=date(2026, 4, 10),
                priority=Priority.P1,
                risk_labels=["risk:api"],
                is_gate=True,
            )
        ]
        result = build_timeline([], items, today=TODAY)
        ti = result.groups[0].items[0]
        assert ti.id == "42"
        assert ti.title == "Important"
        assert ti.status == ItemStatus.IN_PROGRESS
        assert ti.priority == Priority.P1
        assert ti.risk_labels == ["risk:api"]
        assert ti.is_gate is True
