"""Pilot tests for ``ProjectStatePane`` orchestrator bootstrap.

Spec (post-baseline-filter):

- Plans already in ``master.json`` when canon launches are *baseline* —
  they are NOT auto-opened. The pane stays hidden, no tab is mounted.
  These plans are surfaced in the section's running-plans list (rendered
  inside the empty-state pane) for the user to pick on demand.
- A plan slug that *appears* in ``master.json`` after canon is up — i.e.
  an orch run started during this canon session — IS auto-opened: pane
  reveals, plan execution section is shown, a tab is mounted with a
  slug-derived id.
- With no ``master.json`` at all, the section still renders an empty
  placeholder so the user can find the feature.

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
    """Pre-existing plans don't auto-open; in-session arrivals do."""

    @pytest.mark.asyncio
    async def test_existing_plan_does_not_auto_open(
        self, tmp_path: Path
    ) -> None:
        """Canon launched into a project with a running plan stays silent."""
        _write_master_json(tmp_path)
        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            await pilot.pause()
            section = pane.query_one(PlanExecutionSection)
            assert SLUG not in section.open_slugs
            # Running-plans list is populated so the user can open it.
            assert any(p.slug == SLUG for p in section._listed_plans)

    @pytest.mark.asyncio
    async def test_in_session_plan_auto_opens(self, tmp_path: Path) -> None:
        """A new plan slug arriving after canon launch opens its tab."""
        # Master.json starts empty — establishes empty baseline.
        master = tmp_path / ".orchestrator" / "master.json"
        master.parent.mkdir(parents=True)
        master.write_text(json.dumps({"plans": []}), encoding="utf-8")

        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()

            # Now write a new plan — simulates an orch run started while
            # canon is up.
            _write_master_json(tmp_path)
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            section = pane.query_one(PlanExecutionSection)
            assert pane.display is True
            assert section.display is True
            assert SLUG in section.open_slugs
            tab = pane.query_one(PlanExecutionTab)
            assert tab.id == f"plan-tab-{SLUG}"


# ----------------------------------------------------------------------
# Tests — idle / no-orch state
# ----------------------------------------------------------------------


class TestZombieList:
    """Running-plans list surfaces zombies and exposes cleanup actions."""

    @pytest.mark.asyncio
    async def test_zombie_plan_is_listed_with_cleanup_buttons(
        self, tmp_path: Path
    ) -> None:
        """A stale running plan shows up with Mark-crashed + Remove buttons."""
        # Build a master.json with one plan whose updatedAt is way in the
        # past — guaranteed stale.
        plans_dir = tmp_path / ".orchestrator" / "plans" / SLUG
        plans_dir.mkdir(parents=True)
        master = tmp_path / ".orchestrator" / "master.json"
        master.write_text(
            json.dumps(
                {
                    "plans": [
                        {
                            "slug": SLUG,
                            "status": "running",
                            "statePath": "",
                            "startedAt": "2020-01-01T00:00:00Z",
                            "updatedAt": "2020-01-01T00:00:00Z",
                            "progress": {
                                "total": 1,
                                "done": 0,
                                "running": 0,
                                "failed": 0,
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            await pilot.pause()

            # User clicks the Mark-crashed button on the zombie row.
            from toad.widgets.plan_execution_section import (
                PlanExecutionSection as _S,
            )

            section = pane.query_one(_S)
            section.show_section = lambda *_: None  # type: ignore[assignment]
            from textual.widgets import Button

            crash_btn = section.query_one(
                f"#plan-crash-{SLUG}", Button
            )
            crash_btn.press()
            await pilot.pause()
            await pilot.pause()

            # master.json now reports the plan as crashed.
            data = json.loads(master.read_text(encoding="utf-8"))
            entry = next(p for p in data["plans"] if p["slug"] == SLUG)
            assert entry["status"] == "crashed"

    @pytest.mark.asyncio
    async def test_remove_button_drops_plan_from_master_json(
        self, tmp_path: Path
    ) -> None:
        plans_dir = tmp_path / ".orchestrator" / "plans" / SLUG
        plans_dir.mkdir(parents=True)
        master = tmp_path / ".orchestrator" / "master.json"
        master.write_text(
            json.dumps(
                {
                    "plans": [
                        {
                            "slug": SLUG,
                            "status": "running",
                            "statePath": "",
                            "startedAt": "2020-01-01T00:00:00Z",
                            "updatedAt": "2020-01-01T00:00:00Z",
                            "progress": {
                                "total": 1,
                                "done": 0,
                                "running": 0,
                                "failed": 0,
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        app = _Harness(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            pane = app.query_one(ProjectStatePane)
            pane.configure_plan_execution(_make_factory())
            await pilot.pause()
            await pilot.pause()

            from textual.widgets import Button

            remove_btn = pane.query_one(
                f"#plan-remove-{SLUG}", Button
            )
            remove_btn.press()
            await pilot.pause()
            await pilot.pause()

            data = json.loads(master.read_text(encoding="utf-8"))
            assert all(p["slug"] != SLUG for p in data["plans"])


class TestPanelRoute:
    """The plan_execution panel route opens the section without auto-mounting tabs."""

    @pytest.mark.asyncio
    async def test_panel_route_registered(self) -> None:
        """The route exists and points at the plan-exec section."""
        from toad.widgets.project_state_pane import PANEL_ROUTES
        from toad.widgets.plan_execution_section import (
            PlanExecutionSection as _S,
        )

        assert "plan_execution" in PANEL_ROUTES
        section_id, _tab_id = PANEL_ROUTES["plan_execution"]
        assert section_id == _S.SECTION_ID


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
