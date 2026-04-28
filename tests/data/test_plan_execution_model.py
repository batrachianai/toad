"""Pilot tests for ``toad.data.plan_execution_model.PlanExecutionModel``.

The model watches an orchestrator plan directory
(``.orchestrator/plans/<slug>/``) for changes to ``state.json`` and
per-item ``logs/<id>.log`` files, then posts Textual messages that the
existing plan-execution widgets handle:

- ``PlanExecutionTab.ItemStatusChanged`` when an item's ``status`` flips
- ``PlanWorkerLogPane.ItemLogAppended`` (delivered through the
  ``subscribe_log`` callback) when a log file grows
- ``PlanExecutionTab.PlanFinished`` when the plan reaches a terminal
  verdict

These pilot tests pin the public surface of the model. They use polling
mode (no real filesystem watcher thread) and a synchronous ``poll_now``
hook so behaviour is deterministic across platforms.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from toad.data.plan_execution_model import PlanExecutionModel
from toad.widgets.plan_execution_tab import PlanExecutionTab
from toad.widgets.plan_worker_log_pane import PlanWorkerLogPane


# ----------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------


@dataclass
class _Recorder:
    """Captures messages the model would post to a Textual widget."""

    messages: list[Any] = field(default_factory=list)

    def post_message(self, message: Any) -> bool:
        self.messages.append(message)
        return True


def _state_payload(
    *,
    items: Iterable[dict[str, Any]],
    verdict: str | None = None,
    issue_number: int | None = 42,
    slug: str = "20260427-test-plan",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "plan": slug,
        "issueNumber": issue_number,
        "items": list(items),
    }
    if verdict is not None:
        payload["finalReview"] = {"verdict": verdict}
    return payload


def _write_state(plan_dir: Path, payload: dict[str, Any]) -> None:
    (plan_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    """Create an orchestrator plan dir with a minimal ``state.json``."""
    pdir = tmp_path / ".orchestrator" / "plans" / "20260427-test-plan"
    (pdir / "logs").mkdir(parents=True)
    _write_state(
        pdir,
        _state_payload(
            items=[
                {
                    "id": 1,
                    "description": "alpha",
                    "deps": [],
                    "status": "running",
                },
                {
                    "id": 2,
                    "description": "beta",
                    "deps": [1],
                    "status": "queued",
                },
            ],
        ),
    )
    return pdir


# ----------------------------------------------------------------------
# Initial parse
# ----------------------------------------------------------------------


class TestInitialParse:
    """The model parses ``state.json`` on construction."""

    def test_exposes_slug_issue_items_and_verdict(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)

        assert model.slug == "20260427-test-plan"
        assert model.issue_number == 42
        assert [item.id for item in model.items] == [1, 2]
        assert [item.status for item in model.items] == ["running", "queued"]
        assert model.items[1].deps == (1,)
        assert model.verdict == "running"

    def test_no_messages_posted_on_construction(self, plan_dir: Path) -> None:
        """Initial parse populates state but emits nothing."""
        target = _Recorder()
        PlanExecutionModel(plan_dir, target=target, poll=True)
        assert target.messages == []


# ----------------------------------------------------------------------
# ItemStatusChanged
# ----------------------------------------------------------------------


class TestItemStatusChanged:
    """Status flips in ``state.json`` produce ``ItemStatusChanged``."""

    def test_emits_when_item_status_flips(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)
        model.start()
        try:
            _write_state(
                plan_dir,
                _state_payload(
                    items=[
                        {
                            "id": 1,
                            "description": "alpha",
                            "deps": [],
                            "status": "done",
                        },
                        {
                            "id": 2,
                            "description": "beta",
                            "deps": [1],
                            "status": "running",
                        },
                    ],
                ),
            )
            model.poll_now()
        finally:
            model.stop()

        flips = [
            (m.item_id, m.status)
            for m in target.messages
            if isinstance(m, PlanExecutionTab.ItemStatusChanged)
        ]
        assert (1, "done") in flips
        assert (2, "running") in flips

    def test_no_message_when_status_unchanged(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)
        model.start()
        try:
            # Re-write the same payload — nothing changed.
            _write_state(
                plan_dir,
                _state_payload(
                    items=[
                        {
                            "id": 1,
                            "description": "alpha",
                            "deps": [],
                            "status": "running",
                        },
                        {
                            "id": 2,
                            "description": "beta",
                            "deps": [1],
                            "status": "queued",
                        },
                    ],
                ),
            )
            model.poll_now()
        finally:
            model.stop()

        flips = [
            m
            for m in target.messages
            if isinstance(m, PlanExecutionTab.ItemStatusChanged)
        ]
        assert flips == []


# ----------------------------------------------------------------------
# ItemLogAppended
# ----------------------------------------------------------------------


class TestItemLogAppended:
    """New lines in ``logs/<id>.log`` reach ``subscribe_log`` callbacks."""

    def test_subscriber_receives_appended_text(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)
        received: list[str] = []
        unsubscribe = model.subscribe_log(1, received.append)
        model.start()
        try:
            log_path = plan_dir / "logs" / "1.log"
            log_path.write_text("first line\n", encoding="utf-8")
            model.poll_now()
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("second line\n")
            model.poll_now()
        finally:
            unsubscribe()
            model.stop()

        joined = "".join(received)
        assert "first line" in joined
        assert "second line" in joined

    def test_unsubscribe_stops_delivery(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)
        received: list[str] = []
        unsubscribe = model.subscribe_log(1, received.append)
        model.start()
        try:
            log_path = plan_dir / "logs" / "1.log"
            log_path.write_text("before unsub\n", encoding="utf-8")
            model.poll_now()
            unsubscribe()
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("after unsub\n")
            model.poll_now()
        finally:
            model.stop()

        joined = "".join(received)
        assert "before unsub" in joined
        assert "after unsub" not in joined

    def test_log_pane_message_class_is_used(self, plan_dir: Path) -> None:
        """The log-append message class lives on ``PlanWorkerLogPane``.

        This is a regression pin — if the class is renamed or moved, the
        worker-log pane and the model both break together, so make the
        symbol's home explicit.
        """
        assert hasattr(PlanWorkerLogPane, "ItemLogAppended")


# ----------------------------------------------------------------------
# PlanFinished
# ----------------------------------------------------------------------


class TestPlanFinished:
    """A terminal verdict in ``state.json`` produces ``PlanFinished``."""

    def test_emits_when_verdict_set(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)
        model.start()
        try:
            _write_state(
                plan_dir,
                _state_payload(
                    items=[
                        {
                            "id": 1,
                            "description": "alpha",
                            "deps": [],
                            "status": "done",
                        },
                        {
                            "id": 2,
                            "description": "beta",
                            "deps": [1],
                            "status": "done",
                        },
                    ],
                    verdict="SHIP",
                ),
            )
            model.poll_now()
        finally:
            model.stop()

        finished = [
            m for m in target.messages if isinstance(m, PlanExecutionTab.PlanFinished)
        ]
        assert len(finished) == 1
        assert finished[0].verdict == "SHIP"
        assert model.verdict == "SHIP"

    def test_emits_at_most_once_per_terminal_verdict(self, plan_dir: Path) -> None:
        target = _Recorder()
        model = PlanExecutionModel(plan_dir, target=target, poll=True)
        model.start()
        try:
            payload = _state_payload(
                items=[
                    {
                        "id": 1,
                        "description": "alpha",
                        "deps": [],
                        "status": "done",
                    },
                    {
                        "id": 2,
                        "description": "beta",
                        "deps": [1],
                        "status": "done",
                    },
                ],
                verdict="SHIP",
            )
            _write_state(plan_dir, payload)
            model.poll_now()
            # A second poll without any state change must not re-emit.
            model.poll_now()
        finally:
            model.stop()

        finished = [
            m for m in target.messages if isinstance(m, PlanExecutionTab.PlanFinished)
        ]
        assert len(finished) == 1
