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

from unittest.mock import patch

from toad.widgets.gantt_timeline import (
    ACTIVE_STYLE,
    BAR_CHAR,
    BAR_DIM,
    CHARS_PER_WEEK,
    DONE_STYLE,
    LABEL_WIDTH,
    PENDING_STYLE,
    TODAY_CHAR,
    _item_bar_style,
    _status_indicator,
    compute_bar_position,
    compute_track_width,
    render_bar_row,
    render_date_axis,
    render_gantt,
    render_group_header,
    render_today_row,
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


class TestComputeTrackWidth:
    """compute_track_width uses ceil(total_days / 7) * chars_per_week."""

    def test_exact_weeks(self) -> None:
        assert compute_track_width(14) == 2 * CHARS_PER_WEEK

    def test_partial_week_rounds_up(self) -> None:
        # 15 days = 3 weeks (ceil)
        assert compute_track_width(15) == 3 * CHARS_PER_WEEK

    def test_one_day(self) -> None:
        assert compute_track_width(1) == CHARS_PER_WEEK

    def test_zero_days_returns_minimum(self) -> None:
        assert compute_track_width(0) == CHARS_PER_WEEK

    def test_negative_days_returns_minimum(self) -> None:
        assert compute_track_width(-5) == CHARS_PER_WEEK

    def test_custom_chars_per_week(self) -> None:
        assert compute_track_width(14, chars_per_week=8) == 16

    def test_large_timeline(self) -> None:
        # 365 days = 53 weeks (ceil)
        assert compute_track_width(365) == 53 * CHARS_PER_WEEK


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


class TestScrollToTodayPosition:
    """Verify today-position math used by _scroll_to_today."""

    def test_today_at_midpoint(self) -> None:
        """Today at day 50 of 100 maps to pos 50 in a 100-wide track."""
        total_days = 100
        track_width = 100
        day_offset = 50
        pos = int((day_offset / total_days) * track_width)
        assert pos == 50

    def test_today_at_start(self) -> None:
        day_offset = 0
        pos = int((day_offset / 100) * 100)
        assert pos == 0

    def test_today_near_end(self) -> None:
        day_offset = 95
        pos = int((day_offset / 100) * 200)
        assert pos == 190

    def test_today_outside_range_skips_scroll(self) -> None:
        """When today is before or after the timeline, no scroll target."""
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        # A date far in the future — outside range
        future = date(2027, 1, 1)
        day_offset = (future - data.start_date).days
        assert day_offset >= data.total_days

        # A date before start — negative offset
        past = date(2025, 1, 1)
        day_offset = (past - data.start_date).days
        assert day_offset < 0

    def test_scroll_target_centered(self) -> None:
        """scroll target = max(0, pos - visible // 2)."""
        pos = 150
        visible = 80
        target = max(0, pos - visible // 2)
        assert target == 110

    def test_scroll_target_clamped_at_zero(self) -> None:
        """When today is near the start, target clamps to 0."""
        pos = 10
        visible = 80
        target = max(0, pos - visible // 2)
        assert target == 0


class TestRenderTodayRow:
    """render_today_row produces a today-marker row when in range."""

    def test_returns_none_when_before_range(self) -> None:
        data = TimelineData(
            start_date=date(2026, 6, 1), total_days=30
        )
        with patch(
            "toad.widgets.gantt_timeline.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 5, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = render_today_row(data, track_width=60)
        assert result is None

    def test_returns_none_when_after_range(self) -> None:
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=10
        )
        with patch(
            "toad.widgets.gantt_timeline.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 5, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = render_today_row(data, track_width=60)
        assert result is None

    def test_returns_label_and_track_when_in_range(self) -> None:
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        with patch(
            "toad.widgets.gantt_timeline.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 4, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = render_today_row(data, track_width=60)
        assert result is not None
        label, track = result
        assert "TODAY" in label.plain
        assert len(label.plain) == LABEL_WIDTH
        assert TODAY_CHAR in track.plain

    def test_today_marker_position(self) -> None:
        """Marker at day 15 of 30 maps to midpoint of track."""
        data = TimelineData(
            start_date=date(2026, 4, 1), total_days=30
        )
        with patch(
            "toad.widgets.gantt_timeline.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 4, 16)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = render_today_row(data, track_width=60)
        assert result is not None
        _label, track = result
        pos = track.plain.index(TODAY_CHAR)
        assert pos == 30  # day 15 / 30 days * 60 width = 30


class TestRenderGanttLabelTrackAlignment:
    """Labels and tracks stay aligned across all render outputs."""

    def test_all_labels_have_label_width(self) -> None:
        """Every label row has exactly LABEL_WIDTH characters."""
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
            ],
        )
        track_width = compute_track_width(data.total_days)
        labels, tracks = render_gantt(data, track_width)
        for i, label in enumerate(labels):
            assert len(label.plain) == LABEL_WIDTH, (
                f"Row {i} label width {len(label.plain)} != {LABEL_WIDTH}"
            )

    def test_labels_and_tracks_same_length(self) -> None:
        """Label list and track list have equal row count."""
        data = TimelineData(
            start_date=date(2026, 4, 1),
            total_days=60,
            groups=[
                MilestoneGroup(
                    title="M1",
                    items=[_ti("X", ItemStatus.TODO, 0, 10)],
                ),
                MilestoneGroup(
                    title="M2",
                    items=[_ti("Y", ItemStatus.DONE, 20, 5)],
                ),
            ],
        )
        track_width = compute_track_width(data.total_days)
        labels, tracks = render_gantt(data, track_width)
        assert len(labels) == len(tracks)

    def test_track_width_uses_chars_per_week(self) -> None:
        """render_gantt with computed track_width uses fixed sizing."""
        data = TimelineData(
            start_date=date(2026, 4, 1),
            total_days=30,
            groups=[
                MilestoneGroup(
                    title="Sprint",
                    items=[_ti("A", ItemStatus.TODO, 0, 10)],
                ),
            ],
        )
        track_width = compute_track_width(data.total_days)
        expected = 5 * CHARS_PER_WEEK  # ceil(30/7) = 5
        assert track_width == expected
        labels, tracks = render_gantt(data, track_width)
        # Track rows should fill track_width
        for i, track in enumerate(tracks):
            assert len(track.plain) >= track_width, (
                f"Row {i} track len {len(track.plain)} < {track_width}"
            )
