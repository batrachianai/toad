"""PlanExecutionModel — watch an orchestrator plan directory.

Reads ``.orchestrator/plans/<slug>/state.json`` plus per-item
``logs/<id>.log`` files and posts the Textual messages the existing
plan-execution widgets already handle:

- :class:`toad.widgets.plan_execution_tab.PlanExecutionTab.ItemStatusChanged`
  whenever an item's ``status`` field flips,
- :class:`toad.widgets.plan_execution_tab.PlanExecutionTab.PlanFinished`
  the first time ``finalReview.verdict`` reaches a terminal value
  (``SHIP`` or ``REVISE``),
- log chunks delivered through callbacks registered via
  :meth:`subscribe_log` — the path the
  :class:`toad.widgets.plan_worker_log_pane.PlanWorkerLogPane` already
  drives to raise its ``ItemLogAppended`` message.

The model owns no Textual widgets and does no rendering. Construction
parses ``state.json`` once so callers can introspect ``slug``,
``issue_number``, ``items``, and ``verdict`` synchronously. After
:meth:`start`, every call to :meth:`poll_now` rescans the plan
directory and posts whatever changed.

Polling mode (the default, ``poll=True``) gives tests a deterministic,
synchronous trigger and avoids spawning a watcher thread. Production
callers should still use ``poll=True`` and drive :meth:`poll_now` from
a Textual interval — file watching is intentionally out of scope here.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from toad.widgets.plan_dep_graph import DepGraphItem
from toad.widgets.plan_execution_tab import PlanExecutionTab


__all__ = ["PlanExecutionModel"]


_TERMINAL_VERDICTS = frozenset({"SHIP", "REVISE"})
_DEFAULT_VERDICT = "running"


class _MessageTarget(Protocol):
    """Slice of ``textual.widget.Widget`` the model needs."""

    def post_message(self, message: Any) -> bool: ...


class PlanExecutionModel:
    """Polls an orchestrator plan directory and posts widget messages."""

    def __init__(
        self,
        plan_dir: Path,
        *,
        target: _MessageTarget,
        poll: bool = True,
    ) -> None:
        self._plan_dir = Path(plan_dir)
        self._target = target
        self._poll_only = poll
        self._lock = threading.Lock()

        self._slug: str = ""
        self._issue_number: int | None = None
        self._items: list[DepGraphItem] = []
        self._verdict: str = _DEFAULT_VERDICT
        self._finished_emitted: bool = False
        self._started: bool = False

        self._log_positions: dict[int, int] = {}
        self._log_subscribers: dict[int, list[Callable[[str], None]]] = {}

        self._initial_parse()

    # ------------------------------------------------------------------
    # Public attributes
    # ------------------------------------------------------------------

    @property
    def plan_dir(self) -> Path:
        return self._plan_dir

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def issue_number(self) -> int | None:
        return self._issue_number

    @property
    def items(self) -> list[DepGraphItem]:
        """Snapshot of plan items in the order ``state.json`` lists them."""
        return list(self._items)

    @property
    def verdict(self) -> str:
        return self._verdict

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark the model as live; subsequent ``poll_now`` calls emit diffs."""
        self._started = True

    def stop(self) -> None:
        """Stop emitting diffs. Idempotent."""
        self._started = False

    def poll_now(self) -> None:
        """Synchronous rescan — read ``state.json`` and tail subscribed logs."""
        self._scan_state()
        self._scan_logs()

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        """Subscribe ``callback`` to item ``item_id``'s log stream.

        The returned callable removes the subscription. After the last
        subscriber for an item unsubscribes, the model stops tailing
        that item's log file until a new subscription arrives.
        """
        with self._lock:
            self._log_subscribers.setdefault(item_id, []).append(callback)

        def _unsubscribe() -> None:
            with self._lock:
                subs = self._log_subscribers.get(item_id)
                if subs is None:
                    return
                try:
                    subs.remove(callback)
                except ValueError:
                    pass
                if not subs:
                    self._log_subscribers.pop(item_id, None)

        return _unsubscribe

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _initial_parse(self) -> None:
        payload = self._read_state()
        if payload is None:
            return
        self._slug = str(payload.get("plan", ""))
        issue = payload.get("issueNumber")
        self._issue_number = int(issue) if isinstance(issue, int) else None
        self._items = [self._item_from_dict(it) for it in payload.get("items", [])]
        verdict = self._extract_verdict(payload)
        self._verdict = verdict
        if verdict in _TERMINAL_VERDICTS:
            # Treat plans that are already terminal at construction as
            # having been announced — we don't replay history.
            self._finished_emitted = True

    def _scan_state(self) -> None:
        payload = self._read_state()
        if payload is None:
            return
        new_items = [self._item_from_dict(it) for it in payload.get("items", [])]
        old_status: dict[int, str] = {it.id: it.status for it in self._items}
        for item in new_items:
            prev = old_status.get(item.id)
            if prev is not None and prev != item.status:
                self._target.post_message(
                    PlanExecutionTab.ItemStatusChanged(item.id, item.status)
                )
        self._items = new_items

        verdict = self._extract_verdict(payload)
        self._verdict = verdict
        if verdict in _TERMINAL_VERDICTS and not self._finished_emitted:
            self._finished_emitted = True
            self._target.post_message(PlanExecutionTab.PlanFinished(verdict))

    def _scan_logs(self) -> None:
        with self._lock:
            ids = list(self._log_subscribers.keys())
        for item_id in ids:
            log_path = self._plan_dir / "logs" / f"{item_id}.log"
            if not log_path.exists():
                continue
            pos = self._log_positions.get(item_id, 0)
            try:
                size = log_path.stat().st_size
            except OSError:
                continue
            if size <= pos:
                continue
            try:
                with log_path.open("r", encoding="utf-8") as fh:
                    fh.seek(pos)
                    chunk = fh.read()
                    new_pos = fh.tell()
            except OSError:
                continue
            self._log_positions[item_id] = new_pos
            if not chunk:
                continue
            with self._lock:
                callbacks = list(self._log_subscribers.get(item_id, ()))
            for cb in callbacks:
                cb(chunk)

    def _read_state(self) -> dict[str, Any] | None:
        path = self._plan_dir / "state.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _extract_verdict(payload: dict[str, Any]) -> str:
        review = payload.get("finalReview")
        if isinstance(review, dict):
            value = review.get("verdict")
            if isinstance(value, str) and value:
                return value
        return _DEFAULT_VERDICT

    @staticmethod
    def _item_from_dict(data: dict[str, Any]) -> DepGraphItem:
        return DepGraphItem(
            id=int(data["id"]),
            description=str(data.get("description", "")),
            status=str(data.get("status", "queued")),
            deps=tuple(int(d) for d in data.get("deps", [])),
        )
