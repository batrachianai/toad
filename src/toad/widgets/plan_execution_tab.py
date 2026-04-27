"""PlanExecutionTab — ``TabPane`` for one plan (running or historical).

Composes the four plan sub-widgets into a single TabPane:

- A header ``Static`` showing the plan slug, GitHub issue #, counts
  (done / total), overall verdict, and the ACP agent name flowing
  through from Canon's existing picker.
- A :class:`PlanDepGraph` occupying the main area.
- A :class:`PlanWorkerLogPane` tailing the currently selected item.
- A :class:`PlanStatusRail` footer with per-item glyphs and the verdict
  badge.

The tab is deliberately "dumb": data and log streams arrive through an
injected model (Phase B's ``PlanExecutionModel``) and through typed
messages posted to the tab (``ItemsChanged``, ``ItemStatusChanged``,
``PlanFinished``). No file I/O happens here.

After a ``PlanFinished`` message the verdict badge flips but the tab
stays mounted — historical record of the run — until the user closes
it from :class:`PlanExecutionSection`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Static, TabPane

from toad.directory_watcher import DirectoryChanged, DirectoryWatcher
from toad.widgets.plan_dep_graph import DepGraphItem, PlanDepGraph
from toad.widgets.plan_status_rail import PlanStatusRail, RailItem
from toad.widgets.plan_worker_log_pane import PlanWorkerLogPane


_POLL_INTERVAL_SECONDS = 2.5


__all__ = [
    "PlanExecutionModel",
    "PlanExecutionTab",
]


@runtime_checkable
class PlanExecutionModel(Protocol):
    """Protocol slice of Phase B's ``PlanExecutionModel`` used by the tab."""

    slug: str
    issue_number: int | None
    items: Sequence[DepGraphItem]
    verdict: str
    plan_dir: Path

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        """Subscribe to a single item's log stream. Returns an unsubscribe."""

    def poll_now(self) -> None:
        """Rescan the plan directory and post any diffs."""


_DEFAULT_AGENT = "—"


class PlanExecutionTab(TabPane):
    """One-plan tab composing header + dep graph + worker log + status rail."""

    DEFAULT_CSS = """
    PlanExecutionTab #plan-exec-header {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    PlanExecutionTab Vertical.plan-exec-body {
        height: 1fr;
    }
    """

    class ItemsChanged(Message):
        """Replace the plan's items (reflows graph and rail)."""

        def __init__(self, items: Sequence[DepGraphItem]) -> None:
            super().__init__()
            self.items = list(items)

    class ItemStatusChanged(Message):
        """Flip a single item's status without rebuilding the widget tree."""

        def __init__(self, item_id: int, status: str) -> None:
            super().__init__()
            self.item_id = item_id
            self.status = status

    class PlanFinished(Message):
        """Plan reached terminal state; verdict is SHIP or REVISE."""

        def __init__(self, verdict: str) -> None:
            super().__init__()
            self.verdict = verdict

    def __init__(
        self,
        *,
        model: PlanExecutionModel,
        get_current_agent: Callable[[], str] | None = None,
        title: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            title if title is not None else model.slug,
            id=id,
            classes=classes,
        )
        self._model = model
        self._get_current_agent = get_current_agent
        self._items: list[DepGraphItem] = list(model.items)
        self._verdict: str = model.verdict
        self._selected_item_id: int | None = None
        self._poll_timer: Timer | None = None
        self._watcher: DirectoryWatcher | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        plan_dir = self._model.plan_dir
        if plan_dir.is_dir():
            self._watcher = DirectoryWatcher(plan_dir, self)
            self._watcher.daemon = True
            self._watcher.start()
        self._poll_timer = self.set_interval(
            _POLL_INTERVAL_SECONDS, self._model.poll_now
        )

    def on_unmount(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def on_directory_changed(self, _event: DirectoryChanged) -> None:
        self._model.poll_now()

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(classes="plan-exec-body"):
            yield Static(self._compute_header_text(), id="plan-exec-header")
            yield PlanDepGraph(items=self._items, id="plan-exec-graph")
            yield PlanWorkerLogPane(
                model=self._model,
                item_id=None,
                id="plan-exec-log",
            )
            yield PlanStatusRail(
                items=self._rail_items(),
                verdict=self._verdict,
                id="plan-exec-rail",
            )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def header_text(self) -> str:
        """Return the current header string (handy for assertions)."""
        return self._compute_header_text()

    @property
    def selected_item_id(self) -> int | None:
        return self._selected_item_id

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_plan_dep_graph_item_selected(
        self, event: PlanDepGraph.ItemSelected
    ) -> None:
        """Route graph selection into the worker-log pane."""
        event.stop()
        self._selected_item_id = event.item_id
        log = self.query_one(PlanWorkerLogPane)
        log.set_item_id(event.item_id)

    def on_plan_execution_tab_items_changed(self, event: ItemsChanged) -> None:
        event.stop()
        self._items = list(event.items)
        self.query_one(PlanDepGraph).set_items(self._items)
        self.query_one(PlanStatusRail).set_items(self._rail_items())
        self._refresh_header()

    def on_plan_execution_tab_item_status_changed(
        self, event: ItemStatusChanged
    ) -> None:
        event.stop()
        for index, item in enumerate(self._items):
            if item.id == event.item_id:
                self._items[index] = DepGraphItem(
                    id=item.id,
                    description=item.description,
                    status=event.status,
                    deps=item.deps,
                )
                break
        self.query_one(PlanDepGraph).set_items(self._items)
        self.query_one(PlanStatusRail).post_message(
            PlanStatusRail.ItemStatusChanged(event.item_id, event.status)
        )
        self._refresh_header()

    def on_plan_execution_tab_plan_finished(self, event: PlanFinished) -> None:
        """Flip verdict on completion. Tab stays mounted."""
        event.stop()
        self._verdict = event.verdict
        self.query_one(PlanStatusRail).set_verdict(event.verdict)
        self._refresh_header()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rail_items(self) -> list[RailItem]:
        return [RailItem(id=i.id, status=i.status) for i in self._items]

    def _refresh_header(self) -> None:
        header = self.query_one("#plan-exec-header", Static)
        header.update(self._compute_header_text())

    def _compute_header_text(self) -> str:
        slug = self._model.slug
        issue = self._model.issue_number
        done = sum(1 for item in self._items if item.status == "done")
        total = len(self._items)
        agent = (
            self._get_current_agent() if self._get_current_agent else _DEFAULT_AGENT
        )
        parts = [slug]
        if issue is not None:
            parts.append(f"#{issue}")
        parts.append(self._verdict)
        parts.append(f"{done}/{total}")
        parts.append(f"agent: {agent}")
        return "  ".join(parts)
