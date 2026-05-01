"""CanonStateWidget — watches .canon/state.json for canon state."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget

from toad.directory_watcher import DirectoryChanged, DirectoryWatcher

log = logging.getLogger(__name__)

POLL_INTERVAL = 5

BUILD_PHASES = frozenset({"init", "scaffold", "strategy", "develop"})
RUN_PHASES = frozenset({"run"})
ALL_PHASES = BUILD_PHASES | RUN_PHASES


@dataclass(frozen=True)
class LogEntry:
    """A single log entry from canon state."""

    level: str = "info"
    message: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class FlowState:
    """Pipeline flow state from .canon/flow.json."""

    steps: tuple[str, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()
    active: str = ""
    completed: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonState:
    """Parsed canon state from .canon/state.json."""

    phase: str = ""
    status: str = ""
    iteration: int = 0
    error: str | None = None
    logs: tuple[LogEntry, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()
    flow: FlowState | None = None

    @property
    def is_build_phase(self) -> bool:
        return self.phase in BUILD_PHASES

    @property
    def is_run_phase(self) -> bool:
        return self.phase in RUN_PHASES


def _parse_flow(data: dict) -> FlowState:
    """Parse .canon/flow.json into a FlowState."""
    labels_raw = data.get("labels", {})
    labels = tuple((str(k), str(v)) for k, v in labels_raw.items())
    return FlowState(
        steps=tuple(data.get("steps", [])),
        labels=labels,
        active=data.get("active", ""),
        completed=tuple(data.get("completed", [])),
    )


def _parse_state(
    data: dict,
    flow_data: dict | None = None,
) -> CanonState:
    """Parse .canon/state.json into a CanonState."""
    logs_raw = data.get("logs", [])
    logs = tuple(
        LogEntry(
            level=entry.get("level", "info"),
            message=entry.get("msg", entry.get("message", "")),
            # Core writes "ts"; older fixtures used "timestamp". Accept either
            # so the State view shows friendly relative times either way.
            timestamp=entry.get("ts") or entry.get("timestamp") or "",
        )
        for entry in logs_raw
    )

    metrics_raw = data.get("metrics", {})
    metrics = tuple(
        (str(k), str(v)) for k, v in metrics_raw.items()
    )

    flow = _parse_flow(flow_data) if flow_data else None

    return CanonState(
        phase=data.get("phase", ""),
        status=data.get("status", ""),
        iteration=data.get("iteration", 0),
        error=data.get("error"),
        logs=logs,
        metrics=metrics,
        flow=flow,
    )


class CanonStateWidget(Widget):
    """Watches ``.canon/state.json`` for canon build/run state.

    Posts :class:`CanonStateDetected` the first time the file is found.
    Posts :class:`CanonStateUpdated` whenever state changes.
    Exposes reactive ``state`` for child views.
    """

    class CanonStateDetected(Message):
        """Posted once when .canon/state.json is first detected."""

    class CanonStateUpdated(Message):
        """Posted when canon state changes."""

        def __init__(self, state: CanonState) -> None:
            super().__init__()
            self.state = state

    state: reactive[CanonState] = reactive(
        CanonState, always_update=True
    )

    DEFAULT_CSS = """
    CanonStateWidget {
        display: none;
    }
    """

    def __init__(
        self,
        project_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._project_path = project_path or Path(".").resolve()
        self._canon_dir = self._project_path / ".canon"
        self._state_path = self._canon_dir / "state.json"
        self._flow_path = self._canon_dir / "flow.json"
        self._detected = False
        self._last_raw: str | None = None
        self._watcher: DirectoryWatcher | None = None
        self._poll_timer: Timer | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._start_watching()
        self._poll_timer = self.set_interval(
            POLL_INTERVAL, self._poll_state
        )
        self._poll_state()

    def on_unmount(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    # ------------------------------------------------------------------
    # File watcher
    # ------------------------------------------------------------------

    def _start_watching(self) -> None:
        """Start watchdog on .canon/ if the directory exists."""
        if not self._canon_dir.is_dir():
            return
        self._watcher = DirectoryWatcher(self._canon_dir, self)
        self._watcher.daemon = True
        self._watcher.start()

    def on_directory_changed(self, _event: DirectoryChanged) -> None:
        """Watchdog detected a filesystem change — reload state."""
        self._poll_state()

    # ------------------------------------------------------------------
    # Polling / state load
    # ------------------------------------------------------------------

    def _poll_state(self) -> None:
        """Read .canon/state.json (+ flow.json) and refresh state."""
        if self._watcher is None or not self._watcher.enabled:
            self._start_watching()

        if not self._state_path.is_file():
            return

        try:
            state_raw = self._state_path.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Failed to read .canon/state.json: %s", exc)
            return

        # Read flow.json alongside state.json
        flow_raw = ""
        if self._flow_path.is_file():
            try:
                flow_raw = self._flow_path.read_text(encoding="utf-8")
            except OSError:
                pass

        combined = state_raw + flow_raw
        if combined == self._last_raw:
            return
        self._last_raw = combined

        try:
            data = json.loads(state_raw)
        except json.JSONDecodeError as exc:
            log.warning("Invalid JSON in .canon/state.json: %s", exc)
            return

        flow_data = None
        if flow_raw:
            try:
                flow_data = json.loads(flow_raw)
            except json.JSONDecodeError:
                pass

        if not self._detected:
            self._detected = True
            self.post_message(self.CanonStateDetected())

        new_state = _parse_state(data, flow_data)
        self.state = new_state
        self.post_message(self.CanonStateUpdated(new_state))
