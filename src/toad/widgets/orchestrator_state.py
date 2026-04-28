"""OrchestratorStateWidget — watches .orchestrator/ for plan state."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget

from toad.directory_watcher import DirectoryChanged, DirectoryWatcher

log = logging.getLogger(__name__)

POLL_INTERVAL = 5

# A plan with status="running" is considered zombie / stale when its
# updatedAt is older than this many seconds. Orch heartbeats every 30s,
# so 90s = three missed polls.
STALE_THRESHOLD_SECONDS = 90


def _parse_iso_utc(raw: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (with optional trailing 'Z') to UTC."""
    if not raw:
        return None
    try:
        # Python 3.11+ accepts 'Z'; older versions need it stripped.
        text = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_stale(
    plan: PlanSummary,
    *,
    now: datetime | None = None,
    threshold_seconds: int = STALE_THRESHOLD_SECONDS,
) -> bool:
    """Return True if plan is "running" but hasn't been updated recently.

    A stale plan is one whose tmux session likely died (crash, kill, host
    reboot) leaving an orphan ``status="running"`` entry in master.json.
    """
    if plan.status != "running":
        return False
    updated = _parse_iso_utc(plan.updated_at)
    if updated is None:
        return True  # malformed timestamp on a "running" plan ⇒ treat as stale
    now = now or datetime.now(timezone.utc)
    return (now - updated).total_seconds() > threshold_seconds


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


def _patch_plan_status(data: dict, slug: str, status: str) -> bool:
    """Set ``status`` on the named plan entry. Returns True if patched."""
    plans = data.get("plans")
    if not isinstance(plans, list):
        return False
    for entry in plans:
        if isinstance(entry, dict) and entry.get("slug") == slug:
            entry["status"] = status
            entry["updatedAt"] = (
                datetime.now(timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            return True
    return False


def _drop_plan(data: dict, slug: str) -> bool:
    """Remove the named plan entry from ``data["plans"]``. Returns True
    if a plan was removed.
    """
    plans = data.get("plans")
    if not isinstance(plans, list):
        return False
    filtered = [
        e for e in plans
        if not (isinstance(e, dict) and e.get("slug") == slug)
    ]
    if len(filtered) == len(plans):
        return False
    data["plans"] = filtered
    return True


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
        """Posted when the plan list changes.

        ``baseline_slugs`` is the set of slugs that existed in
        ``master.json`` the first time the widget read it — i.e. plans
        that were already there when canon launched. Subscribers use
        this to skip auto-opening pre-existing plans (only auto-open
        plans started during the current canon session).
        """

        def __init__(
            self,
            plans: list[PlanSummary],
            baseline_slugs: frozenset[str],
        ) -> None:
            super().__init__()
            self.plans = plans
            self.baseline_slugs = baseline_slugs

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
        # Slugs already present in master.json when canon first read it.
        # Stays empty until the first successful poll, then frozen for the
        # rest of the canon session.
        self._baseline_slugs: frozenset[str] = frozenset()
        self._baseline_captured = False

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
        if not self._baseline_captured:
            self._baseline_slugs = frozenset(p.slug for p in new_plans if p.slug)
            self._baseline_captured = True
        self.plans = new_plans
        self.post_message(
            self.PlansUpdated(new_plans, self._baseline_slugs)
        )

        # Auto-select first plan if none selected
        if self._selected_slug is None and new_plans:
            self.select_plan(new_plans[0].slug)
        elif self._selected_slug is not None:
            self._load_plan_items(self._selected_slug)

    def select_plan(self, slug: str) -> None:
        """Select a plan and load its items from state.json."""
        self._selected_slug = slug
        self._load_plan_items(slug)

    # ------------------------------------------------------------------
    # master.json mutations — used for zombie cleanup actions
    # ------------------------------------------------------------------

    def mark_plan_crashed(self, slug: str) -> bool:
        """Patch the named plan's entry to ``status: "crashed"``.

        Returns True on success, False if master.json is missing or the
        slug isn't present. Does not touch the plan's directory.
        """
        return self._mutate_master(
            lambda data: _patch_plan_status(data, slug, "crashed")
        )

    def remove_plan_from_list(self, slug: str) -> bool:
        """Drop the named plan from ``master.json.plans``.

        Returns True on success. The plan's ``.orchestrator/plans/<slug>/``
        directory is left intact so logs survive.
        """
        return self._mutate_master(
            lambda data: _drop_plan(data, slug)
        )

    def _mutate_master(
        self, mutator: Callable[[dict], bool]
    ) -> bool:
        if not self._master_path.is_file():
            return False
        try:
            data = json.loads(
                self._master_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to read master.json for mutation: %s", exc)
            return False
        if not mutator(data):
            return False
        try:
            self._master_path.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("Failed to write master.json: %s", exc)
            return False
        # Refresh state so the UI sees the mutation right away.
        self._poll_state()
        return True

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
