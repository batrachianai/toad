"""OrchestratorStateWidget — watches .orchestrator/ for plan state."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget

from toad.directory_watcher import DirectoryChanged, DirectoryWatcher

log = logging.getLogger(__name__)

POLL_INTERVAL = 5


@dataclass(frozen=True)
class PlanProgress:
    """Aggregated progress counts for a single plan."""

    total: int = 0
    done: int = 0
    running: int = 0
    failed: int = 0

    @property
    def queued(self) -> int:
        return self.total - self.done - self.running - self.failed


@dataclass(frozen=True)
class PlanSummary:
    """Summary of one orchestrator plan from master.json."""

    slug: str
    status: str
    state_path: str
    started_at: str
    updated_at: str
    progress: PlanProgress = field(default_factory=PlanProgress)


@dataclass(frozen=True)
class PlanItem:
    """A single work item from a per-plan state.json."""

    id: int
    description: str
    status: str
    iteration: int
    max_iterations: int
    last_result: str | None


def _parse_master(data: dict) -> list[PlanSummary]:
    """Parse master.json into PlanSummary list."""
    plans: list[PlanSummary] = []
    for entry in data.get("plans", []):
        prog = entry.get("progress", {})
        plans.append(
            PlanSummary(
                slug=entry.get("slug", ""),
                status=entry.get("status", "unknown"),
                state_path=entry.get("statePath", ""),
                started_at=entry.get("startedAt", ""),
                updated_at=entry.get("updatedAt", ""),
                progress=PlanProgress(
                    total=prog.get("total", 0),
                    done=prog.get("done", 0),
                    running=prog.get("running", 0),
                    failed=prog.get("failed", 0),
                ),
            )
        )
    return plans


def _parse_items(data: dict) -> list[PlanItem]:
    """Parse per-plan state.json into PlanItem list."""
    items: list[PlanItem] = []
    for entry in data.get("items", []):
        items.append(
            PlanItem(
                id=entry.get("id", 0),
                description=entry.get("description", ""),
                status=entry.get("status", "queued"),
                iteration=entry.get("iteration", 0),
                max_iterations=entry.get("maxIterations", 3),
                last_result=entry.get("lastResult"),
            )
        )
    return items


class OrchestratorStateWidget(Widget):
    """Watches ``.orchestrator/`` for plan data.

    Posts :class:`OrchestratorDetected` the first time
    ``master.json`` is found. Exposes reactive ``plans`` and
    ``selected_plan_items`` for child views.
    """

    class OrchestratorDetected(Message):
        """Posted once when master.json is first detected."""

    class PlansUpdated(Message):
        """Posted when the plan list changes."""

        def __init__(self, plans: list[PlanSummary]) -> None:
            super().__init__()
            self.plans = plans

    class ItemsUpdated(Message):
        """Posted when items for the selected plan change."""

        def __init__(self, items: list[PlanItem]) -> None:
            super().__init__()
            self.items = items

    plans: reactive[list[PlanSummary]] = reactive(
        list, always_update=True
    )
    selected_plan_items: reactive[list[PlanItem]] = reactive(
        list, always_update=True
    )

    DEFAULT_CSS = """
    OrchestratorStateWidget {
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
        self._orch_dir = self._project_path / ".orchestrator"
        self._master_path = self._orch_dir / "master.json"
        self._detected = False
        self._selected_slug: str | None = None
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
        # Initial load in case master.json already exists
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
        """Start watchdog on .orchestrator/ if the directory exists."""
        if not self._orch_dir.is_dir():
            return
        self._watcher = DirectoryWatcher(self._orch_dir, self)
        self._watcher.daemon = True
        self._watcher.start()

    def on_directory_changed(self, _event: DirectoryChanged) -> None:
        """Watchdog detected a filesystem change — reload state."""
        self._poll_state()

    # ------------------------------------------------------------------
    # Polling / state load
    # ------------------------------------------------------------------

    def _poll_state(self) -> None:
        """Read master.json and refresh plan data."""
        # If watcher not started yet, try again (dir may have appeared)
        if self._watcher is None or not self._watcher.enabled:
            self._start_watching()

        if not self._master_path.is_file():
            return

        # First detection
        if not self._detected:
            self._detected = True
            self.post_message(self.OrchestratorDetected())

        try:
            raw = json.loads(
                self._master_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to read master.json: %s", exc)
            return

        new_plans = _parse_master(raw)
        self.plans = new_plans
        self.post_message(self.PlansUpdated(new_plans))

        # Auto-select first plan if none selected
        if self._selected_slug is None and new_plans:
            self.select_plan(new_plans[0].slug)
        elif self._selected_slug is not None:
            self._load_plan_items(self._selected_slug)

    def select_plan(self, slug: str) -> None:
        """Select a plan and load its items from state.json."""
        self._selected_slug = slug
        self._load_plan_items(slug)

    def _load_plan_items(self, slug: str) -> None:
        """Read per-plan state.json and update selected_plan_items."""
        state_path = self._orch_dir / "plans" / slug / "state.json"
        if not state_path.is_file():
            self.selected_plan_items = []
            self.post_message(self.ItemsUpdated([]))
            return

        try:
            raw = json.loads(
                state_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            log.warning(
                "Failed to read state.json for %s: %s", slug, exc
            )
            return

        items = _parse_items(raw)
        self.selected_plan_items = items
        self.post_message(self.ItemsUpdated(items))
