"""Gantt Timeline — renders a Gantt chart from TimelineData model."""

from __future__ import annotations

import logging
from datetime import date

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from toad.widgets.github_views.timeline_data import (
    MilestoneGroup,
    TimelineData,
    TimelineItem,
)
from toad.widgets.github_views.timeline_provider import ItemStatus, Priority

log = logging.getLogger(__name__)

# Palette
DONE_STYLE = "green"
ACTIVE_STYLE = "yellow"
PENDING_STYLE = "bright_black"
GATE_STYLE = "bold yellow"
TODAY_STYLE = "bold green"
AXIS_STYLE = "bright_black"
GROUP_STYLE = "bold cyan"
DUE_STYLE = "bold magenta"

# Layout
LABEL_WIDTH = 22
BAR_CHAR = "\u2588"  # █
BAR_DIM = "\u2591"  # ░
TODAY_CHAR = "\u2502"  # │
DIAMOND = "\u25c6"  # ◆

# Priority → style suffix
_PRIORITY_BORDER: dict[Priority, str] = {
    Priority.P1: "bold red",
    Priority.P2: "bold yellow",
    Priority.P3: "",
    Priority.P4: "dim",
}


def _item_bar_style(item: TimelineItem) -> str:
    """Return bar style based on status."""
    if item.status is ItemStatus.DONE:
        return DONE_STYLE
    if item.status is ItemStatus.IN_PROGRESS:
        return ACTIVE_STYLE
    return PENDING_STYLE


def _status_indicator(status: ItemStatus) -> str:
    """Return a status prefix character."""
    if status is ItemStatus.DONE:
        return "\u2713 "  # ✓
    if status is ItemStatus.IN_PROGRESS:
        return "\u25b6 "  # ▶
    return "  "


def compute_bar_position(
    start_day: int,
    days: int,
    total_days: int,
    track_width: int,
) -> tuple[int, int]:
    """Compute character offset and width for a Gantt bar.

    Returns:
        (offset, width) in characters.
    """
    if total_days <= 0 or track_width <= 0:
        return (0, 0)
    offset = int((start_day / total_days) * track_width)
    width = max(1, int((days / total_days) * track_width))
    offset = min(offset, track_width - 1)
    width = min(width, track_width - offset)
    return (offset, width)


def render_date_axis(
    data: TimelineData,
    track_width: int,
) -> list[tuple[Text, Text]]:
    """Build date axis rows: dates on top, gate markers below.

    Returns:
        List of (label, track) pairs — one per axis row.
    """
    total_days = data.total_days
    start = data.start_date

    # Row 1: date tick marks
    date_track = [" "] * track_width
    tick_interval = max(7, total_days // max(1, track_width // 10))
    for day in range(0, total_days, tick_interval):
        pos = int((day / total_days) * track_width)
        if pos + 6 >= track_width:
            break
        d = date.fromordinal(start.toordinal() + day)
        label = d.strftime("%b %d")
        if all(
            date_track[pos + i] == " "
            for i in range(len(label))
            if pos + i < track_width
        ):
            for i, ch in enumerate(label):
                idx = pos + i
                if idx < track_width:
                    date_track[idx] = ch

    date_label = Text(" " * LABEL_WIDTH)
    date_track_text = Text(
        "".join(date_track), style=f"bold {AXIS_STYLE}"
    )

    # Row 2: gate markers
    gate_track = [" "] * track_width
    for gate in data.gates:
        pos = (
            int((gate.day / total_days) * track_width)
            if total_days > 0
            else 0
        )
        pos = min(pos, track_width - 1)
        tag = f"{DIAMOND}{gate.label}"
        for i, ch in enumerate(tag):
            idx = pos + i
            if idx < track_width:
                gate_track[idx] = ch

    gate_str = "".join(gate_track)
    gate_text = Text(gate_str, style=AXIS_STYLE)
    for gate in data.gates:
        pos = (
            int((gate.day / total_days) * track_width)
            if total_days > 0
            else 0
        )
        pos = min(pos, track_width - 1)
        tag = f"{DIAMOND}{gate.label}"
        end = min(pos + len(tag), track_width)
        gate_text.stylize(GATE_STYLE, pos, end)

    gate_label = Text(" " * LABEL_WIDTH)

    return [(date_label, date_track_text), (gate_label, gate_text)]


def render_today_row(
    data: TimelineData,
    track_width: int,
) -> tuple[Text, Text] | None:
    """Build a today-marker row if today falls within the timeline range.

    Returns:
        (label, track) pair, or None if today is outside the range.
    """
    today = date.today()
    day_offset = (today - data.start_date).days
    if day_offset < 0 or day_offset >= data.total_days:
        return None

    pos = int((day_offset / data.total_days) * track_width)
    pos = min(pos, track_width - 1)

    label = Text("TODAY".ljust(LABEL_WIDTH), style=TODAY_STYLE)
    track = Text(
        " " * pos + TODAY_CHAR + " " * (track_width - pos - 1),
        style=TODAY_STYLE,
    )
    return (label, track)


def render_bar_row(
    item: TimelineItem,
    total_days: int,
    track_width: int,
) -> tuple[Text, Text]:
    """Render one Gantt bar row: label and positioned bar track.

    Returns:
        (label, track) pair.
    """
    indicator = _status_indicator(item.status)
    raw_label = item.title
    label_str = (indicator + raw_label)[: LABEL_WIDTH - 1].ljust(
        LABEL_WIDTH
    )
    style = _item_bar_style(item)

    offset, width = compute_bar_position(
        item.start_day,
        item.days,
        total_days,
        track_width,
    )

    done = item.status is ItemStatus.DONE
    char = BAR_CHAR if done else BAR_DIM

    # Priority styling on the label
    priority_style = ""
    if item.priority and item.priority in _PRIORITY_BORDER:
        priority_style = _PRIORITY_BORDER[item.priority]
    label_style = priority_style or (f"dim {style}" if done else style)

    # Risk items get underlined bars
    bar_style = f"underline {style}" if item.risk_labels else style

    label = Text(label_str, style=label_style)

    track = Text(" " * offset)
    track.append(char * width, style=bar_style)
    remaining = track_width - offset - width
    if remaining > 0:
        track.append(" " * remaining)

    return (label, track)


def render_group_header(
    group: MilestoneGroup,
    data: TimelineData,
    track_width: int,
) -> tuple[Text, Text]:
    """Render a milestone group header with optional due-date marker.

    Returns:
        (label, track) pair.
    """
    title = f"\u2501\u2501 {group.title} "
    label = Text(
        title[: LABEL_WIDTH - 1].ljust(LABEL_WIDTH), style=GROUP_STYLE
    )

    track_chars = ["\u2500"] * track_width
    if group.due_date:
        day_offset = (group.due_date - data.start_date).days
        if 0 <= day_offset < data.total_days:
            pos = int((day_offset / data.total_days) * track_width)
            pos = min(pos, track_width - 1)
            due_label = f"{DIAMOND}{group.due_date.strftime('%b %d')}"
            for i, ch in enumerate(due_label):
                idx = pos + i
                if idx < track_width:
                    track_chars[idx] = ch

    track = Text("".join(track_chars), style=AXIS_STYLE)
    if group.due_date:
        day_offset = (group.due_date - data.start_date).days
        if 0 <= day_offset < data.total_days:
            pos = int((day_offset / data.total_days) * track_width)
            pos = min(pos, track_width - 1)
            due_label = f"{DIAMOND}{group.due_date.strftime('%b %d')}"
            end = min(pos + len(due_label), track_width)
            track.stylize(DUE_STYLE, pos, end)

    return (label, track)


def render_gantt(
    data: TimelineData,
    track_width: int = 60,
) -> tuple[list[Text], list[Text]]:
    """Render the full Gantt chart as parallel label and track lists.

    Returns:
        (labels, tracks) — same-length lists for the label column
        and the scrollable track column.
    """
    labels: list[Text] = []
    tracks: list[Text] = []

    # Date axis (dates + gate markers = 2 rows)
    for lbl, trk in render_date_axis(data, track_width):
        labels.append(lbl)
        tracks.append(trk)

    # Separator
    labels.append(Text(" " * LABEL_WIDTH, style=AXIS_STYLE))
    tracks.append(Text("\u2500" * track_width, style=AXIS_STYLE))

    # Today marker
    today = render_today_row(data, track_width)
    if today:
        labels.append(today[0])
        tracks.append(today[1])

    # Milestone groups with headers
    for group in data.groups:
        lbl, trk = render_group_header(group, data, track_width)
        labels.append(lbl)
        tracks.append(trk)
        for item in group.items:
            lbl, trk = render_bar_row(
                item, data.total_days, track_width
            )
            labels.append(lbl)
            tracks.append(trk)

    return (labels, tracks)


class GanttTimeline(Static):
    """A Textual widget that renders a Gantt chart from TimelineData."""

    DEFAULT_CSS = """
    GanttTimeline {
        height: auto;
        padding: 0 1;
    }
    """

    timeline_data: reactive[TimelineData | None] = reactive(None)

    def watch_timeline_data(self) -> None:
        """Re-render when data changes."""
        self._render_chart()

    def on_resize(self) -> None:
        """Re-render on terminal resize."""
        if self.timeline_data:
            self._render_chart()

    def _render_chart(self) -> None:
        """Render the Gantt chart into this widget."""
        if not self.timeline_data:
            self.update("No timeline data")
            return
        width = self.size.width if self.size.width > 0 else 80
        track_width = max(40, width - LABEL_WIDTH - 4)
        labels, track_parts = render_gantt(
            self.timeline_data, track_width
        )
        combined: list[Text] = []
        for lbl, trk in zip(labels, track_parts):
            line = lbl.copy()
            line.append_text(trk)
            combined.append(line)
        self.update(Text("\n").join(combined))
