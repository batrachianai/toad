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
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Static, TabPane

from toad.directory_watcher import DirectoryChanged, DirectoryWatcher
from toad.widgets.plan_dep_graph import DepGraphItem, PlanDepGraph
from toad.widgets.plan_donut import PlanDonut
from toad.widgets.plan_worker_log_pane import PlanWorkerLogPane

if TYPE_CHECKING:
    from toad.data.plan_execution_model import TerminalInfo


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

    def set_target(self, target: Any) -> None:
        """Re-point the model's message sink at the given widget."""


_DEFAULT_AGENT = "—"


class PlanExecutionTab(TabPane):
    """One-plan tab composing header + dep graph + worker log + status rail."""

    DEFAULT_CSS = """
    PlanExecutionTab #plan-exec-header-row {
        height: auto;
        max-height: 3;
        background: $panel;
    }
    PlanExecutionTab #plan-exec-header-text {
        height: auto;
        background: $panel;
        color: $text;
        padding: 0 1;
        width: 1fr;
    }
    PlanExecutionTab PlanDonut {
        width: 12;
        height: 2;
        margin: 0 1 0 0;
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
        """Plan reached terminal state.

        ``verdict`` carries the rail badge label — typically ``SHIP`` or
        ``REVISE`` from ``finalReview.result``, or ``FAILED`` / ``ABORTED``
        when the engine bails out without a final review.

        ``terminal`` carries the structured snapshot (PR URL, verification,
        summary) the tab uses to render the completion banner. ``None``
        when the message comes from a caller that hasn't built one (some
        tests post a bare verdict).
        """

        def __init__(
            self,
            verdict: str,
            terminal: "TerminalInfo | None" = None,
        ) -> None:
            super().__init__()
            self.verdict = verdict
            self.terminal = terminal

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
        self._terminal: "TerminalInfo | None" = getattr(model, "terminal", None)
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
            with Horizontal(id="plan-exec-header-row"):
                yield Static(
                    self._compute_header_text(),
                    id="plan-exec-header-text",
                )
                yield PlanDonut(
                    items=self._items,
                    id="plan-exec-donut",
                )
            yield PlanDepGraph(items=self._items, id="plan-exec-graph")
            yield PlanWorkerLogPane(
                model=self._model,
                item_id=None,
                id="plan-exec-log",
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
        self.query_one(PlanDonut).set_items(self._items)
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
        self.query_one(PlanDonut).set_items(self._items)
        self._refresh_header()

    def on_plan_execution_tab_plan_finished(self, event: PlanFinished) -> None:
        """Flip verdict on completion. Tab stays mounted."""
        event.stop()
        self._verdict = event.verdict
        if event.terminal is not None:
            self._terminal = event.terminal
        self.query_one(PlanDonut).set_items(self._items)
        self._refresh_header()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _refresh_header(self) -> None:
        header = self.query_one("#plan-exec-header-text", Static)
        header.update(self._compute_header_text())

    def _compute_header_text(self) -> str:
        slug = self._model.slug
        issue = self._model.issue_number
        done = sum(1 for item in self._items if item.status == "done")
        running = sum(1 for item in self._items if item.status == "running")
        failed = sum(1 for item in self._items if item.status == "failed")
        total = len(self._items)
        agent = (
            self._get_current_agent() if self._get_current_agent else _DEFAULT_AGENT
        )
        terminal = self._terminal

        parts: list[str] = [slug]
        if issue is not None:
            parts.append(f"#{issue}")
        parts.append(self._status_badge(terminal))
        parts.append(f"{done}/{total}")
        if terminal is None and running:
            parts.append(f"◉{running}")
        if failed:
            parts.append(f"✗{failed}")
        if terminal is not None and terminal.pr_number is not None:
            parts.append(f"PR #{terminal.pr_number}")
        if terminal is not None and terminal.elapsed_seconds is not None:
            parts.append(_format_elapsed(terminal.elapsed_seconds))
        parts.append(f"agent: {agent}")
        first_line = "  ".join(parts)

        details = self._format_terminal_details()
        if details:
            return f"{first_line}\n{details}"
        return first_line

    def _status_badge(self, terminal: "TerminalInfo | None") -> str:
        """One-token state for the header — keeps the rail's signal at the top."""
        if terminal is not None:
            if terminal.status == "completed":
                if terminal.result == "SHIP" or self._verdict == "SHIP":
                    return "✓ Completed (SHIP)"
                if terminal.result == "REVISE" or self._verdict == "REVISE":
                    return "✗ Completed (REVISE)"
                return "✓ Completed"
            if terminal.status == "failed":
                return f"✗ Failed ({self._verdict})" if self._verdict not in {
                    "running", "FAILED"
                } else "✗ Failed"
            if terminal.status == "aborted":
                return "⊘ Aborted"
        # No terminal payload — the verdict alone may carry the result if a
        # caller posted ``PlanFinished("SHIP")`` without building a snapshot.
        if self._verdict == "SHIP":
            return "✓ Completed (SHIP)"
        if self._verdict == "REVISE":
            return "✗ Completed (REVISE)"
        if self._verdict in {"FAILED", "ABORTED"}:
            return f"✗ {self._verdict.title()}"
        # Live run: prefer model.phase (lowercased so existing fixtures stay
        # green and the badge reads as a state, not a heading).
        phase = getattr(self._model, "phase", _phase_from_verdict(self._verdict))
        return f"⟲ {phase.lower()}" if phase else self._verdict

    def _format_terminal_details(self) -> str:
        """Second header line — only used when there's something extra to say."""
        terminal = self._terminal
        if terminal is None:
            return ""
        bits: list[str] = []
        if terminal.pr_url:
            bits.append(terminal.pr_url)
        if terminal.verification_status:
            verify = f"verify: {terminal.verification_status}"
            if terminal.verification_unchecked:
                verify += f" ({terminal.verification_unchecked} unchecked)"
            bits.append(verify)
        if terminal.items_reworked:
            bits.append(f"{terminal.items_reworked} reworked")
        if terminal.review_iterations:
            bits.append(f"{terminal.review_iterations} reviews")
        return "  ".join(bits)


def _phase_from_verdict(verdict: str) -> str:
    if verdict == "SHIP":
        return "Done"
    if verdict in {"REVISE", "FAILED", "ABORTED"}:
        return "Failed"
    return "Running"


def _format_elapsed(seconds: float) -> str:
    total = int(seconds)
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {sec:02d}s"
    return f"{minutes}m {sec:02d}s"
