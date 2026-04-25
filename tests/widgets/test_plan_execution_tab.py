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

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from textual.app import App, ComposeResult
from textual.widgets import TabbedContent

from toad.widgets.plan_dep_graph import DepGraphItem, PlanDepGraph
from toad.widgets.plan_execution_tab import PlanExecutionTab
from toad.widgets.plan_status_rail import PlanStatusRail
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
    subscriptions: list[_Subscription] = field(default_factory=list)

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        sub = _Subscription(item_id=item_id, callback=callback)
        self.subscriptions.append(sub)

        def _unsubscribe() -> None:
            sub.unsubscribed = True

        return _unsubscribe


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
    """Header shows slug, issue #, counts, verdict, and agent name."""

    @pytest.mark.asyncio
    async def test_header_shows_slug_issue_counts_and_agent(self) -> None:
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model, agent="claude")
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            header_text = tab.header_text()
            assert model.slug in header_text
            assert "#42" in header_text
            assert "1/4" in header_text  # one "done" out of four items
            assert "running" in header_text
            assert "claude" in header_text

    @pytest.mark.asyncio
    async def test_header_reflects_agent_callable(self) -> None:
        model = _FakeModel(items=_fixture_items())
        app = _Harness(model, agent="codex")
        async with app.run_test() as pilot:
            await pilot.pause()
            tab = app.query_one(PlanExecutionTab)
            assert "codex" in tab.header_text()

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
            rail = tab.query_one(PlanStatusRail)
            assert rail.verdict_label() == "SHIP"
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
            rail = tab.query_one(PlanStatusRail)
            assert rail.verdict_label() == "REVISE"
            assert "REVISE" in tab.header_text()
            # Still mounted inside the TabbedContent.
            tabs = app.query_one(TabbedContent)
            assert tab.id in {pane.id for pane in tabs.query(PlanExecutionTab)}
