"""Tests for Gantt timeline rendering.

Verifies:
- compute_bar_position math (offset, width, edge cases)
- render_bar_row produces correct structure per status, priority, risk
- render_group_header shows milestone title and due-date marker
- render_date_axis includes gate markers
- render_gantt assembles full output
- _item_bar_style and _status_indicator return correct values
"""

from __future__ import annotations

from datetime import date

from toad.widgets.gantt_timeline import (
    ACTIVE_STYLE,
    BAR_CHAR,
    BAR_DIM,
    DONE_STYLE,
    LABEL_WIDTH,
    PENDING_STYLE,
    _item_bar_style,
    _status_indicator,
    compute_bar_position,
    render_bar_row,
    render_date_axis,
    render_gantt,
    render_group_header,
)
from toad.widgets.github_views.timeline_data import (
    GateMarker,
    MilestoneGroup,
    TimelineData,
    TimelineItem,
)
from toad.widgets.github_views.timeline_provider import (
    ItemStatus,
    Priority,
)


def _ti(
    title: str = "Task",
    status: ItemStatus = ItemStatus.TODO,
    start_day: int = 0,
    days: int = 5,
    is_gate: bool = False,
    priority: Priority | None = None,
    risk_labels: list[str] | None = None,
) -> TimelineItem:
    return TimelineItem(
        id="1",
        title=title,
        status=status,
        start_day=start_day,
        days=days,
        is_gate=is_gate,
        priority=priority,
        risk_labels=risk_labels or [],
    )


class TestComputeBarPosition:
    """compute_bar_position maps day offsets to character positions."""

    def test_basic_position(self) -> None:
        offset, width = compute_bar_position(
            start_day=0, days=10, total_days=100, track_width=100
        )
        assert offset == 0
        assert width == 10

    def test_midpoint(self) -> None:
        offset, width = compute_bar_position(
            start_day=50, days=10, total_days=100, track_width=100
        )
        assert offset == 50
        assert width == 10

    def test_minimum_width_one(self) -> None:
        offset, width = compute_bar_position(
            start_day=0, days=1, total_days=1000, track_width=60
        )
        assert width >= 1

    def test_zero_total_days(self) -> None:
        assert compute_bar_position(0, 5, 0, 60) == (0, 0)

    def test_zero_track_width(self) -> None:
        assert compute_bar_position(0, 5, 10, 0) == (0, 0)

    def test_bar_clamped_to_track(self) -> None:
        offset, width = compute_bar_position(
            start_day=95, days=20, total_days=100, track_width=100
        )
        assert offset + width <= 100


class TestItemBarStyle:
    """_item_bar_style returns correct style per status."""

    def test_done(self) -> None:
        assert _item_bar_style(_ti(status=ItemStatus.DONE)) == DONE_STYLE

    def test_in_progress(self) -> None:
        result = _item_bar_style(_ti(status=ItemStatus.IN_PROGRESS))
        assert result == ACTIVE_STYLE

    def test_todo(self) -> None:
        assert _item_bar_style(_ti(status=ItemStatus.TODO)) == PENDING_STYLE


class TestStatusIndicator:
    """_status_indicator returns prefix characters per status."""

    def test_done_checkmark(self) -> None:
        assert "\u2713" in _status_indicator(ItemStatus.DONE)

    def test_in_progress_triangle(self) -> None:
        assert "\u25b6" in _status_indicator(ItemStatus.IN_PROGRESS)

    def test_todo_blank(self) -> None:
        assert _status_indicator(ItemStatus.TODO).strip() == ""


class TestRenderBarRow:
    """render_bar_row produces styled Rich Text for a Gantt bar."""

    def test_done_item_uses_solid_bar(self) -> None:
        item = _ti("Done Task", status=ItemStatus.DONE, start_day=0, days=10)
        label, track = render_bar_row(item, total_days=100, track_width=100)
        assert BAR_CHAR in track.plain

    def test_todo_item_uses_dim_bar(self) -> None:
        item = _ti("Todo Task", status=ItemStatus.TODO, start_day=0, days=10)
        label, track = render_bar_row(item, total_days=100, track_width=100)
        assert BAR_DIM in track.plain

    def test_label_truncated_to_width(self) -> None:
        long_name = "A" * 50
        item = _ti(long_name, start_day=0, days=10)
        label, track = render_bar_row(item, total_days=100, track_width=100)
        assert len(label.plain) == LABEL_WIDTH

    def test_risk_labels_present(self) -> None:
        item = _ti(risk_labels=["risk:api"])
        label, track = render_bar_row(item, total_days=100, track_width=60)
        assert len(track.plain) > 0


class TestRenderGroupHeader:
    """render_group_header shows milestone title and optional due-date."""

    def test_title_in_output(self) -> None:
        group = MilestoneGroup(title="Sprint 1", items=[])
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        label, track = render_group_header(group, data, track_width=60)
        assert "Sprint 1" in label.plain

    def test_due_date_marker(self) -> None:
        group = MilestoneGroup(
            title="Sprint 1",
            due_date=date(2026, 4, 15),
            items=[],
        )
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        label, track = render_group_header(group, data, track_width=60)
        assert "\u25c6" in track.plain

    def test_no_due_date_no_diamond(self) -> None:
        group = MilestoneGroup(title="Sprint 1", items=[])
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        label, track = render_group_header(group, data, track_width=60)
        assert "\u25c6" not in track.plain


class TestRenderDateAxis:
    """render_date_axis builds date ticks and gate markers."""

    def test_returns_two_rows(self) -> None:
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        rows = render_date_axis(data, track_width=60)
        assert len(rows) == 2
        # Each row is a (label, track) tuple
        for label, track in rows:
            assert len(label.plain) == LABEL_WIDTH

    def test_gate_markers_in_second_row(self) -> None:
        data = TimelineData(
            start_date=date(2026, 4, 1),
            total_days=30,
            gates=[GateMarker(label="GA", day=10)],
        )
        rows = render_date_axis(data, track_width=60)
        _label, track = rows[1]
        assert "GA" in track.plain


class TestRenderGantt:
    """render_gantt assembles the full chart."""

    def test_full_render_no_crash(self) -> None:
        data = TimelineData(
            start_date=date(2026, 4, 1),
            total_days=30,
            groups=[
                MilestoneGroup(
                    title="Sprint 1",
                    due_date=date(2026, 4, 15),
                    items=[
                        _ti("A", ItemStatus.DONE, 0, 5),
                        _ti("B", ItemStatus.IN_PROGRESS, 5, 10),
                    ],
                ),
                MilestoneGroup(
                    title="Ungrouped",
                    items=[_ti("C", ItemStatus.TODO, 10, 5)],
                ),
            ],
            gates=[GateMarker(label="Gate", day=20)],
        )
        labels, tracks = render_gantt(data, track_width=60)
        assert len(labels) == len(tracks)
        # 2 axis rows + 1 separator + 2 group headers + 3 items = 8 minimum
        assert len(labels) >= 8
        label_text = "\n".join(lbl.plain for lbl in labels)
        assert "Sprint 1" in label_text
        assert "Ungrouped" in label_text

    def test_minimal_data(self) -> None:
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=1
        )
        labels, tracks = render_gantt(data, track_width=60)
        assert len(labels) == len(tracks)
        # At least axis rows + separator
        assert len(labels) >= 3
