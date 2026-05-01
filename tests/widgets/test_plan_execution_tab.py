"""Tests for the ``PlanExecutionTab`` widget.

The ``PlanExecutionTab`` is a ``TabPane`` subclass that composes four
children — a header, a ``PlanDepGraph``, a ``PlanWorkerLogPane``, and a
``PlanStatusRail`` — to render one plan (running or historical).

These tests drive:

- Header shows plan slug, GitHub issue number, counts (done/total), the
  overall verdict, and the ACP agent name injected via ``get_current_agent``.
- Selecting a node in the dep graph (via a ``PlanDepGraph.ItemSelected``
  message) switches the worker-log pane to that item.
- When a ``PlanFinished`` message lands the rail verdict flips to SHIP /
  REVISE, *and* the tab stays mounted (historical record).

The tab is intentionally dumb — data arrives through an injected model
(Phase B's ``PlanExecutionModel``). The tests use a fake model.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import TabbedContent

from toad.data.plan_execution_model import PlanExecutionModel
from toad.directory_watcher import DirectoryWatcher
from toad.widgets.plan_dep_graph import DepGraphItem, PlanDepGraph
from toad.widgets.plan_execution_tab import PlanExecutionTab
from toad.widgets.plan_worker_log_pane import PlanWorkerLogPane


# ------------------------------------------------------------------
# Test doubles
# ------------------------------------------------------------------


@dataclass
class _Subscription:
    item_id: int
    callback: Callable[[str], None]
    unsubscribed: bool = False


@dataclass
class _FakeModel:
    """Stand-in for Phase B's ``PlanExecutionModel``."""

    slug: str = "20260422-demo-plan"
    issue_number: int | None = 42
    items: list[DepGraphItem] = field(default_factory=list)
    verdict: str = "running"
    plan_dir: Path = field(default_factory=lambda: Path("/nonexistent-fake-plan"))
    subscriptions: list[_Subscription] = field(default_factory=list)

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        sub = _Subscription(item_id=item_id, callback=callback)
        self.subscriptions.append(sub)

        def _unsubscribe() -> None:
            sub.unsubscribed = True

        return _unsubscribe

    def poll_now(self) -> None:
        return None


def _fixture_items() -> list[DepGraphItem]:
    return [
        DepGraphItem(id=1, description="alpha", status="done"),
        DepGraphItem(id=2, description="beta", status="running", deps=(1,)),
        DepGraphItem(id=3, description="gamma", status="queued", deps=(2,)),
        DepGraphItem(id=4, description="delta", status="queued", deps=(3,)),
    ]


class _Harness(App[None]):
    """Mounts one ``PlanExecutionTab`` inside a ``TabbedContent``."""

    def __init__(
        self,
        model: _FakeModel,
        agent: str = "claude",
    ) -> None:
        super().__init__()
        self._model = model
        self._agent = agent

    def compose(self) -> ComposeResult:
        tabs = TabbedContent(id="plan-exec-tabs")
        with tabs:
            yield PlanExecutionTab(
                model=self._model,
                get_current_agent=lambda: self._agent,
                id="plan-tab-demo",
            )


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------


class TestHeader:
    """Header shows slug, issue #, counts, and badge."""

    @pytest.mark.asyncio
    async def test_header_shows_slug_issue_counts_and_badge(self) -> None:
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            header_text = tab.header_text()
            assert model.slug in header_text
            assert "#42" in header_text
            assert "1/4" in header_text  # one "done" out of four items
            assert "running" in header_text

    @pytest.mark.asyncio
    async def test_header_omits_agent_token(self) -> None:
        """Agent name was removed from the header — assert it stays out."""
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            assert "agent:" not in tab.header_text()

    @pytest.mark.asyncio
    async def test_header_without_issue_number(self) -> None:
        model = _FakeModel(items=_fixture_items(), issue_number=None)
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            text = tab.header_text()
            # No "#N" token when issue_number is None.
            assert "#" not in text


# ------------------------------------------------------------------
# Graph → log routing
# ------------------------------------------------------------------


class TestGraphSelectionRoutesToLog:
    """Selecting a graph node switches the worker-log pane's item id."""

    @pytest.mark.asyncio
    async def test_item_selected_switches_log_pane_item(self) -> None:
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            log = tab.query_one(PlanWorkerLogPane)

            tab.post_message(PlanDepGraph.ItemSelected(2))
            await pilot.pause()
            assert log.item_id == 2

            tab.post_message(PlanDepGraph.ItemSelected(3))
            await pilot.pause()
            assert log.item_id == 3

    @pytest.mark.asyncio
    async def test_switching_item_resubscribes_on_model(self) -> None:
        """Switching items tears down the old log subscription."""
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            tab.post_message(PlanDepGraph.ItemSelected(1))
            await pilot.pause()
            tab.post_message(PlanDepGraph.ItemSelected(2))
            await pilot.pause()
            # Two subscriptions were created; the first was unsubscribed.
            ids = [s.item_id for s in model.subscriptions]
            assert 1 in ids and 2 in ids
            first = next(s for s in model.subscriptions if s.item_id == 1)
            assert first.unsubscribed is True


# ------------------------------------------------------------------
# PlanFinished persistence
# ------------------------------------------------------------------


class TestPlanFinishedPersists:
    """``PlanFinished`` flips the verdict but never unmounts the tab."""

    @pytest.mark.asyncio
    async def test_tab_persists_after_plan_finished_ship(self) -> None:
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            tab.post_message(PlanExecutionTab.PlanFinished("SHIP"))
            await pilot.pause()

            # Tab is still mounted and queryable.
            still_there = app.query_one(PlanExecutionTab)
            assert still_there is tab
            assert "SHIP" in tab.header_text()

    @pytest.mark.asyncio
    async def test_tab_persists_after_plan_finished_revise(self) -> None:
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            tab.post_message(PlanExecutionTab.PlanFinished("REVISE"))
            await pilot.pause()
            assert "REVISE" in tab.header_text()
            # Still mounted inside the TabbedContent.
            tabs = app.query_one(TabbedContent)
            assert tab.id in {pane.id for pane in tabs.query(PlanExecutionTab)}


# ------------------------------------------------------------------
# Live updates — directory watcher + interval backstop
# ------------------------------------------------------------------


def _state_payload(
    items: list[dict[str, Any]],
    *,
    slug: str = "20260427-live-plan",
    issue_number: int | None = 99,
    verdict: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "plan": slug,
        "issueNumber": issue_number,
        "items": items,
    }
    if verdict is not None:
        payload["finalReview"] = {"result": verdict, "status": "done"}
        payload["status"] = "completed"
    return payload


def _write_state(plan_dir: Path, payload: dict[str, Any]) -> None:
    (plan_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def live_plan_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / ".orchestrator" / "plans" / "20260427-live-plan"
    (pdir / "logs").mkdir(parents=True)
    _write_state(
        pdir,
        _state_payload(
            [
                {"id": 1, "description": "alpha", "deps": [], "status": "queued"},
                {"id": 2, "description": "beta", "deps": [1], "status": "queued"},
            ]
        ),
    )
    return pdir


class _LateTarget:
    """Defers ``post_message`` until a real widget is bound after mount."""

    def __init__(self) -> None:
        self.target: Any = None

    def post_message(self, message: Any) -> bool:
        if self.target is None:
            return False
        return bool(self.target.post_message(message))


class _LiveHarness(App[None]):
    def __init__(self, model: PlanExecutionModel) -> None:
        super().__init__()
        self._model = model

    def compose(self) -> ComposeResult:
        tabs = TabbedContent(id="plan-exec-tabs")
        with tabs:
            yield PlanExecutionTab(model=self._model, id="plan-tab-live")


class TestLiveUpdates:
    """Tab installs a watcher + interval on mount; mutations reach the rail."""

    @pytest.mark.asyncio
    async def test_on_mount_installs_timer_and_watcher(
        self, live_plan_dir: Path
    ) -> None:
        target = _LateTarget()
        model = PlanExecutionModel(live_plan_dir, target=target)
        app = _LiveHarness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            target.target = tab

            # Backstop interval timer is installed.
            assert tab._poll_timer is not None  # type: ignore[attr-defined]
            # DirectoryWatcher is installed and points at the plan dir.
            watcher = tab._watcher  # type: ignore[attr-defined]
            assert isinstance(watcher, DirectoryWatcher)

    @pytest.mark.asyncio
    async def test_on_unmount_stops_timer_and_watcher(
        self, live_plan_dir: Path
    ) -> None:
        target = _LateTarget()
        model = PlanExecutionModel(live_plan_dir, target=target)
        app = _LiveHarness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            target.target = tab
            assert tab._poll_timer is not None  # type: ignore[attr-defined]
            assert tab._watcher is not None  # type: ignore[attr-defined]
            tab.remove()
            await pilot.pause()
            assert tab._poll_timer is None  # type: ignore[attr-defined]
            assert tab._watcher is None  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_state_mutation_drives_status_change_through_tab(
        self, live_plan_dir: Path
    ) -> None:
        target = _LateTarget()
        model = PlanExecutionModel(live_plan_dir, target=target)
        model.start()
        app = _LiveHarness(model)
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            target.target = tab

            # Two queued items with no done; header shows "0/2".
            assert "0/2" in tab.header_text()

            # Backstop poll catches this even if watcher misses.
            await pilot.pause()
            _write_state(
                live_plan_dir,
                _state_payload(
                    [
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
                    ]
                ),
            )
            # Allow the 2.5s backstop to fire and the message to drain.
            await pilot.pause(3.0)

            # One running, one queued — header counter still 0/2 done plus
            # an active marker on the live row.
            text = tab.header_text()
            assert "0/2" in text
            assert "◉1" in text
