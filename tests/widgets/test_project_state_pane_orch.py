"""Pilot tests for ``ProjectStatePane`` orchestrator bootstrap.

When Canon starts inside a project that already has a live
``.orchestrator/master.json``, the pane is expected to:

- reveal itself (``display = True``) once
  :class:`OrchestratorStateWidget.PlansUpdated` fires,
- mount a :class:`PlanExecutionSection` and open one tab per plan slug,
- name the tab pane after the slug (so the agent can address it via the
  panel-routing layer).

When no plan is active yet — the pane has been configured for plan
execution but ``master.json`` does not exist — the section must still
expose an empty-state placeholder so the user can find the feature.

These pilots use a stub model factory so no real orchestrator
filesystem watcher runs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from toad.widgets.plan_execution_section import PlanExecutionSection
from toad.widgets.plan_execution_tab import PlanExecutionTab
from toad.widgets.project_state_pane import ProjectStatePane


SLUG = "20260427-test-plan"


# ----------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------


@dataclass
class _StubModel:
    """Protocol-shaped stub of ``PlanExecutionModel``.

    The tab only reads the four scalar attributes plus ``subscribe_log``
    on mount. The pilot does not drive any updates — it just verifies
    bootstrap geometry — so the stub is intentionally inert.
    """

    slug: str
    issue_number: int | None = None
    items: list[Any] = field(default_factory=list)
    verdict: str = "running"
    _unsub_calls: list[int] = field(default_factory=list)

    def subscribe_log(
        self, item_id: int, callback: Callable[[str], None]
    ) -> Callable[[], None]:
        del callback

        def _unsubscribe() -> None:
            self._unsub_calls.append(item_id)

        return _unsubscribe


def _make_factory() -> Callable[[str], _StubModel]:
    def factory(slug: str) -> _StubModel:
        return _StubModel(slug=slug, issue_number=99)

    return factory


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _write_master_json(project_path: Path, slug: str = SLUG) -> Path:
    """Create a fake ``.orchestrator/master.json`` listing one plan."""
    plans_dir = project_path / ".orchestrator" / "plans" / slug
    plans_dir.mkdir(parents=True)
    state_path = plans_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "plan": slug,
                "issueNumber": 99,
                "items": [
                    {
                        "id": 1,
                        "description": "do work",
                        "deps": [],
                        "status": "queued",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    master = project_path / ".orchestrator" / "master.json"
    master.write_text(
        json.dumps(
            {
                "plans": [
                    {
                        "slug": slug,
                        "status": "running",
                        "statePath": str(state_path),
                        "startedAt": "2026-04-27T12:00:00Z",
                        "updatedAt": "2026-04-27T12:00:00Z",
                        "progress": {
                            "total": 1,
                            "done": 0,
                            "running": 0,
                            "failed": 0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return master


# ----------------------------------------------------------------------
# Harness
# ----------------------------------------------------------------------


class _Harness(App[None]):
    """App that mounts a single ``ProjectStatePane`` rooted at ``project_path``."""

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self._project_path = project_path

    def compose(self) -> ComposeResult:
        yield ProjectStatePane(project_path=self._project_path)


# ----------------------------------------------------------------------
# Tests — auto-open on PlansUpdated
# ----------------------------------------------------------------------


class TestPlanExecutionBootstrap:
    """Pane reveals itself and opens a plan tab when ``master.json`` exists."""

    @pytest.mark.asyncio
    async def test_pane_visible_after_plans_updated(self, tmp_path: Path) -> None:
        _write_master_json(tmp_path)
        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            await pilot.pause()
            assert pane.display is True

    @pytest.mark.asyncio
    async def test_section_is_mounted_with_slug_tab(self, tmp_path: Path) -> None:
        _write_master_json(tmp_path)
        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            await pilot.pause()
            section = pane.query_one(PlanExecutionSection)
            assert section.display is True
            assert SLUG in section.open_slugs

    @pytest.mark.asyncio
    async def test_tab_id_matches_slug(self, tmp_path: Path) -> None:
        _write_master_json(tmp_path)
        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            await pilot.pause()
            tab = pane.query_one(PlanExecutionTab)
            assert tab.id == f"plan-tab-{SLUG}"


# ----------------------------------------------------------------------
# Tests — idle / no-orch state
# ----------------------------------------------------------------------


class TestIdlePlaceholder:
    """With no ``master.json`` the section shows an empty-state placeholder."""

    @pytest.mark.asyncio
    async def test_empty_state_visible_before_any_plan(
        self, tmp_path: Path
    ) -> None:
        # No .orchestrator dir at all — pane is in idle state.
        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            section = pane.query_one(PlanExecutionSection)
            placeholders = [
                node
                for node in section.query(Static)
                if "empty-state" in node.classes
            ]
            assert placeholders, (
                "PlanExecutionSection must render an empty-state placeholder "
                "when no plan is open"
            )
