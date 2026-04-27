"""Tests for ``PlanExecutionSection``.

Two contracts are exercised:

- **Empty state.** When no plan tabs are open the section renders a
  single placeholder ``TabPane`` containing a ``Static`` with the
  ``empty-state`` class. Opening the first real tab removes the
  placeholder; closing the last real tab restores it.
- **Persistent finished tabs.** ``PlanExecutionSection`` has no hook
  that automatically removes a tab when its slug drops out of
  ``master.json`` — finished tabs stay mounted until the user closes
  them explicitly via :meth:`close_tab`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static, TabbedContent, TabPane

from toad.widgets.plan_execution_section import (
    EMPTY_PANE_ID,
    PlanExecutionSection,
)
from toad.widgets.plan_execution_tab import PlanExecutionTab


# ----------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------


@dataclass
class _StubModel:
    slug: str
    issue_number: int | None = 7
    items: list[Any] = field(default_factory=list)
    verdict: str = "running"

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        del item_id, callback
        return lambda: None


def _factory(slug: str) -> _StubModel:
    return _StubModel(slug=slug)


class _Harness(App[None]):
    def __init__(self, *, with_factory: bool = True) -> None:
        super().__init__()
        self._with_factory = with_factory

    def compose(self) -> ComposeResult:
        yield PlanExecutionSection(
            model_factory=_factory if self._with_factory else None,
            id=PlanExecutionSection.SECTION_ID,
        )


def _empty_state_statics(section: PlanExecutionSection) -> list[Static]:
    return [
        node
        for node in section.query(Static)
        if "empty-state" in node.classes
    ]


# ----------------------------------------------------------------------
# Empty state
# ----------------------------------------------------------------------


class TestEmptyState:
    @pytest.mark.asyncio
    async def test_placeholder_pane_present_when_no_tabs(self) -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            tabs = section.query_one("#plan-exec-tabs", TabbedContent)
            pane_ids = {pane.id for pane in tabs.query(TabPane)}
            assert EMPTY_PANE_ID in pane_ids
            assert _empty_state_statics(section), (
                "section must render a Static.empty-state when idle"
            )

    @pytest.mark.asyncio
    async def test_placeholder_removed_after_first_tab_opens(self) -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            section.open_tab("alpha")
            await pilot.pause()
            await pilot.pause()
            tabs = section.query_one("#plan-exec-tabs", TabbedContent)
            pane_ids = {pane.id for pane in tabs.query(TabPane)}
            assert EMPTY_PANE_ID not in pane_ids
            assert "plan-tab-alpha" in pane_ids

    @pytest.mark.asyncio
    async def test_placeholder_restored_after_last_tab_closes(self) -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            section.open_tab("alpha")
            await pilot.pause()
            await pilot.pause()
            section.close_tab("alpha")
            await pilot.pause()
            await pilot.pause()
            tabs = section.query_one("#plan-exec-tabs", TabbedContent)
            pane_ids = {pane.id for pane in tabs.query(TabPane)}
            assert EMPTY_PANE_ID in pane_ids
            assert _empty_state_statics(section)

    @pytest.mark.asyncio
    async def test_placeholder_present_without_factory(self) -> None:
        app = _Harness(with_factory=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            assert _empty_state_statics(section)


# ----------------------------------------------------------------------
# Persistent finished tabs
# ----------------------------------------------------------------------


class TestPersistentTabs:
    @pytest.mark.asyncio
    async def test_open_tab_persists_without_explicit_close(self) -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            section.open_tab("alpha")
            await pilot.pause()
            await pilot.pause()
            # Nothing else touches the section. Pump the event loop a few
            # times — there's no auto-close mechanism that should fire.
            for _ in range(3):
                await pilot.pause()
            assert "alpha" in section.open_slugs
            tab = section.query_one("#plan-tab-alpha", PlanExecutionTab)
            assert tab is not None

    @pytest.mark.asyncio
    async def test_finished_tab_kept_when_other_tabs_open(self) -> None:
        """Two tabs open; closing one keeps the other mounted."""
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            section.open_tab("alpha")
            await pilot.pause()
            section.open_tab("beta")
            await pilot.pause()
            await pilot.pause()
            section.close_tab("alpha")
            await pilot.pause()
            await pilot.pause()
            assert "alpha" not in section.open_slugs
            assert "beta" in section.open_slugs
            # Empty placeholder must NOT be present while one tab remains.
            tabs = section.query_one("#plan-exec-tabs", TabbedContent)
            pane_ids = {pane.id for pane in tabs.query(TabPane)}
            assert EMPTY_PANE_ID not in pane_ids
            assert "plan-tab-beta" in pane_ids

    @pytest.mark.asyncio
    async def test_open_tab_idempotent_on_repeated_slug(self) -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            section = app.query_one(PlanExecutionSection)
            first = section.open_tab("alpha")
            await pilot.pause()
            second = section.open_tab("alpha")
            await pilot.pause()
            assert first == second == "plan-tab-alpha"
            tabs = section.query_one("#plan-exec-tabs", TabbedContent)
            slug_panes = [
                pane
                for pane in tabs.query(TabPane)
                if pane.id == "plan-tab-alpha"
            ]
            assert len(slug_panes) == 1
