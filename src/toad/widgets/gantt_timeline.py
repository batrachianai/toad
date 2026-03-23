"""Gantt Timeline — JSON-driven Gantt chart rendered with Rich Text."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

log = logging.getLogger(__name__)

COLOR_MAP: dict[str, str] = {
    "accent": "dodger_blue2",
    "cyan": "cyan",
    "green": "green",
    "orange": "dark_orange",
    "yellow": "yellow",
    "red": "red",
    "purple": "medium_purple",
}

GATE_STYLE = "bold bright_red"
EVENT_STYLE = "bold bright_yellow"
TODAY_STYLE = "bold bright_green"
AXIS_STYLE = "bright_black"
LABEL_WIDTH = 20
BAR_CHAR = "\u2588"  # █
BAR_CHAR_DIM = "\u2591"  # ░
TODAY_CHAR = "\u2502"  # │

STATUS_DONE = "done"
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"


def _resolve_color(name: str) -> str:
    """Map a JSON color name to a Rich style string."""
    return COLOR_MAP.get(name, name)


def _parse_start_date(meta: dict[str, Any]) -> date | None:
    """Parse the startDate from meta, returning None on failure."""
    raw = meta.get("startDate", "")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


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
    # Clamp to track bounds
    offset = min(offset, track_width - 1)
    width = min(width, track_width - offset)
    return (offset, width)


def render_date_axis(
    meta: dict[str, Any],
    gates: list[dict[str, Any]],
    track_width: int,
) -> list[Text]:
    """Build date axis rows: dates on top, gate/event markers below."""
    total_days = meta.get("totalDays", 1)
    start = _parse_start_date(meta)

    # --- Row 1: date tick marks ---
    date_track = [" "] * track_width
    # Space ticks so labels (~6 chars) don't overlap
    tick_interval = max(7, total_days // max(1, track_width // 10))
    for day in range(0, total_days, tick_interval):
        pos = int((day / total_days) * track_width)
        if pos + 6 >= track_width:
            break
        if start:
            d = (
                start
                if day == 0
                else date.fromordinal(start.toordinal() + day)
            )
            label = d.strftime("%b %d")
        else:
            label = f"D{day}"
        # Only place if it won't overlap previous label
        if all(date_track[pos + i] == " " for i in range(len(label)) if pos + i < track_width):
            for i, ch in enumerate(label):
                idx = pos + i
                if idx < track_width:
                    date_track[idx] = ch

    date_line = Text(" " * LABEL_WIDTH)
    date_line.append("".join(date_track), style="bold white")

    # --- Row 2: gate / event markers ---
    gate_track = [" "] * track_width
    gate_line = Text(" " * LABEL_WIDTH)

    for gate in sorted(gates, key=lambda g: g.get("day", 0)):
        day = gate.get("day", 0)
        pos = int((day / total_days) * track_width) if total_days > 0 else 0
        pos = min(pos, track_width - 1)
        marker = gate.get("label", "?")
        style = GATE_STYLE if gate.get("type") == "gate" else EVENT_STYLE
        # Place marker text, preceded by a diamond
        tag = f"\u25c6{marker}"
        for i, ch in enumerate(tag):
            idx = pos + i
            if idx < track_width:
                gate_track[idx] = ch

    # Build styled gate line segment by segment
    gate_str = "".join(gate_track)
    gate_text = Text(gate_str, style=AXIS_STYLE)
    # Re-style each gate marker with its color
    for gate in sorted(gates, key=lambda g: g.get("day", 0)):
        day = gate.get("day", 0)
        pos = int((day / total_days) * track_width) if total_days > 0 else 0
        pos = min(pos, track_width - 1)
        tag = f"\u25c6{gate.get('label', '?')}"
        style = GATE_STYLE if gate.get("type") == "gate" else EVENT_STYLE
        end = min(pos + len(tag), track_width)
        gate_text.stylize(style, pos, end)

    gate_line.append_text(gate_text)

    return [date_line, gate_line]


def render_today_row(
    meta: dict[str, Any],
    track_width: int,
) -> Text | None:
    """Build a today-marker row if today falls within the timeline range."""
    total_days = meta.get("totalDays", 1)
    start = _parse_start_date(meta)
    if not start or total_days <= 0:
        return None

    today = date.today()
    day_offset = (today - start).days
    if day_offset < 0 or day_offset >= total_days:
        return None

    pos = int((day_offset / total_days) * track_width)
    pos = min(pos, track_width - 1)

    label_part = Text("TODAY".ljust(LABEL_WIDTH), style=TODAY_STYLE)
    track = Text(" " * pos + TODAY_CHAR + " " * (track_width - pos - 1), style=TODAY_STYLE)
    label_part.append_text(track)
    return label_part


def _status_indicator(status: str) -> str:
    """Return a status prefix character."""
    if status == STATUS_DONE:
        return "\u2713 "  # ✓
    if status == STATUS_ACTIVE:
        return "\u25b6 "  # ▶
    return "  "


def render_bar_row(
    bar: dict[str, Any],
    total_days: int,
    track_width: int,
) -> Text:
    """Render one Gantt bar row: [status] [label] [positioned bar]."""
    status = bar.get("status", STATUS_PENDING)
    raw_label = bar.get("label", "")
    indicator = _status_indicator(status)
    label = (indicator + raw_label)[:LABEL_WIDTH - 1].ljust(LABEL_WIDTH)
    color = _resolve_color(bar.get("color", "white"))

    offset, width = compute_bar_position(
        bar.get("startDay", 0),
        bar.get("days", 1),
        total_days,
        track_width,
    )

    if status == STATUS_DONE:
        label_style = "dim strike green"
        bar_style = "dim green"
        char = BAR_CHAR
    elif status == STATUS_ACTIVE:
        label_style = "bold bright_white"
        bar_style = f"bold {color}"
        char = BAR_CHAR
    else:
        label_style = "dim"
        bar_style = f"dim {color}"
        char = BAR_CHAR_DIM

    line = Text(label, style=label_style)
    line.append(" " * offset)
    line.append(char * width, style=bar_style)

    remaining = track_width - offset - width
    if remaining > 0:
        line.append(" " * remaining)

    return line


def render_gantt(
    data: dict[str, Any],
    track_width: int = 60,
) -> list[Text]:
    """Render the full Gantt chart as a list of Rich Text lines."""
    meta = data.get("meta", {})
    bars = data.get("ganttBars", [])
    gates = data.get("gates", [])
    total_days = meta.get("totalDays", 1)

    lines: list[Text] = []

    # Date axis (dates + gate markers = 2 rows)
    lines.extend(render_date_axis(meta, gates, track_width))

    # Separator
    sep = Text(" " * LABEL_WIDTH, style=AXIS_STYLE)
    sep.append("\u2500" * track_width, style=AXIS_STYLE)
    lines.append(sep)

    # Today marker
    today_line = render_today_row(meta, track_width)
    if today_line:
        lines.append(today_line)

    # Bar rows
    for bar in bars:
        lines.append(render_bar_row(bar, total_days, track_width))

    return lines


class GanttTimeline(Static):
    """A Textual widget that renders a Gantt chart from JSON timeline data."""

    DEFAULT_CSS = """
    GanttTimeline {
        height: auto;
        padding: 0 1;
    }
    """

    timeline_data: reactive[dict[str, Any] | None] = reactive(None)

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        data_path: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if data is not None:
            self._initial_data = data
        elif data_path is not None:
            self._initial_data = self._load_file(Path(data_path))
        else:
            self._initial_data = None

    def on_mount(self) -> None:
        """Defer initial render until layout is ready."""
        if self._initial_data is not None:
            self.set_timer(0.1, self._deferred_load)

    def _deferred_load(self) -> None:
        """Load data after layout has settled."""
        self.timeline_data = self._initial_data

    @staticmethod
    def _load_file(path: Path) -> dict[str, Any] | None:
        """Load timeline JSON from a file path."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to load timeline data from %s: %s", path, exc)
            return None

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
        lines = render_gantt(self.timeline_data, track_width)
        self.update(Text("\n").join(lines))

    def reload_from_file(self, path: str | Path) -> None:
        """Reload timeline data from a JSON file."""
        self.timeline_data = self._load_file(Path(path))


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    DEMO_PATH = Path(__file__).resolve().parents[4] / "timeline.json"
    # Fallback to the canon-docs reference data
    REFERENCE_PATH = Path(
        "/Users/cerratoa/dega/canon-docs/ace/deliverables/site/data.json"
    )

    class GanttApp(App):
        CSS = """
        Screen {
            overflow-y: auto;
        }
        """

        def compose(self) -> ComposeResult:
            path = DEMO_PATH if DEMO_PATH.exists() else REFERENCE_PATH
            yield GanttTimeline(data_path=path)

    GanttApp().run()
