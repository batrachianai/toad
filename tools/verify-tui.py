#!/usr/bin/env python3
"""Verify TUI widgets render correctly in headless mode.

Usage:
    uv run python tools/verify-tui.py
    uv run python tools/verify-tui.py --verbose
    uv run python tools/verify-tui.py --widget gantt
    uv run python tools/verify-tui.py --widget github
    uv run python tools/verify-tui.py --widget tasks

Runs the app or individual widgets headless and reports layout,
scroll behavior, and rendering issues. Exit code 0 = all checks pass.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from datetime import date

from rich.console import Console

console = Console()


def verify_gantt(verbose: bool = False) -> bool:
    """Verify GanttTimeline widget: rendering, scroll, auto-scroll-to-today."""
    from textual.app import App, ComposeResult
    from textual.containers import ScrollableContainer

    from toad.widgets.gantt_timeline import (
        GanttTimeline,
        compute_track_width,
        render_gantt,
        LABEL_WIDTH,
    )
    from toad.widgets.github_views.timeline_data import (
        GateMarker,
        MilestoneGroup,
        TimelineData,
        TimelineItem,
    )
    from toad.widgets.github_views.timeline_provider import ItemStatus

    errors: list[str] = []
    results: dict[str, object] = {}

    # --- Test 1: Pure render functions ---
    items = [
        TimelineItem("1", "Canon TUI", ItemStatus.DONE, 0, 14),
        TimelineItem("2", "pmxt POC", ItemStatus.DONE, 0, 3, is_gate=True),
        TimelineItem("3", "CLI init", ItemStatus.DONE, 5, 7),
        TimelineItem("4", "CLI register", ItemStatus.IN_PROGRESS, 20, 10),
        TimelineItem("5", "Arena MVP", ItemStatus.TODO, 30, 21),
        TimelineItem("6", "Hackathon", ItemStatus.TODO, 60, 21),
    ]
    groups = [
        MilestoneGroup("Canon TUI", date(2026, 4, 5), [items[0]]),
        MilestoneGroup("pmxt POC", None, [items[1]]),
        MilestoneGroup("Canon CLI", None, [items[2], items[3]]),
        MilestoneGroup("Arena MVP", date(2026, 5, 15), [items[4]]),
        MilestoneGroup("Hackathon", date(2026, 6, 19), [items[5]]),
    ]
    data = TimelineData(
        start_date=date(2026, 3, 19),
        total_days=93,
        groups=groups,
        gates=[GateMarker("pmxt", 0)],
    )

    tw = compute_track_width(data.total_days)
    lines = render_gantt(data, tw)
    total_width = LABEL_WIDTH + tw

    if tw <= 80:
        errors.append(
            f"track_width too small: {tw} (expected >80 for 93-day span)"
        )
    if len(lines) < 10:
        errors.append(f"too few render lines: {len(lines)} (expected >=10)")

    results["track_width"] = tw
    results["total_width"] = total_width
    results["render_lines"] = len(lines)

    # --- Test 2: Widget layout in headless Textual app ---
    class TestApp(App):
        CSS = "Screen { overflow: hidden; }\nGanttTimeline { height: 1fr; }"

        def compose(self) -> ComposeResult:
            yield GanttTimeline(id="gantt")

        def on_mount(self) -> None:
            self.query_one("#gantt", GanttTimeline).timeline_data = data
            self.set_timer(1.5, self._check)

        def _check(self) -> None:
            gantt = self.query_one("#gantt", GanttTimeline)
            scroll = gantt.query_one("#gantt-scroll", ScrollableContainer)
            content = gantt.query_one("#gantt-content")

            results["gantt_size"] = str(gantt.size)
            results["scroll_size"] = str(scroll.size)
            results["virtual_size"] = str(scroll.virtual_size)
            results["content_size"] = str(content.size)
            results["can_scroll_x"] = scroll.allow_horizontal_scroll
            results["can_scroll_y"] = scroll.allow_vertical_scroll
            results["max_scroll_x"] = scroll.max_scroll_x
            results["max_scroll_y"] = scroll.max_scroll_y

            if not scroll.allow_horizontal_scroll:
                errors.append("horizontal scroll not enabled")
            if scroll.max_scroll_x <= 0:
                errors.append(
                    f"max_scroll_x={scroll.max_scroll_x}, expected >0"
                )
            if content.size.width < total_width:
                errors.append(
                    f"content width {content.size.width} < "
                    f"expected {total_width}"
                )

            self.exit()

    TestApp().run(headless=True, size=(80, 25))

    # --- Test 3: Vertical scroll with many groups ---
    many_groups = [
        MilestoneGroup(
            f"M{i}",
            None,
            [
                TimelineItem(f"{i}a", f"T{i}A", ItemStatus.DONE, i * 5, 7),
                TimelineItem(f"{i}b", f"T{i}B", ItemStatus.TODO, i * 5 + 3, 10),
            ],
        )
        for i in range(15)
    ]
    tall_data = TimelineData(
        start_date=date(2026, 3, 19),
        total_days=93,
        groups=many_groups,
        gates=[],
    )

    class TallApp(App):
        CSS = "Screen { overflow: hidden; }\nGanttTimeline { height: 1fr; }"

        def compose(self) -> ComposeResult:
            yield GanttTimeline(id="gantt")

        def on_mount(self) -> None:
            self.query_one("#gantt", GanttTimeline).timeline_data = tall_data
            self.set_timer(1.5, self._check)

        def _check(self) -> None:
            gantt = self.query_one("#gantt", GanttTimeline)
            scroll = gantt.query_one("#gantt-scroll", ScrollableContainer)

            results["vscroll_can_scroll_y"] = scroll.allow_vertical_scroll
            results["vscroll_max_scroll_y"] = scroll.max_scroll_y

            if not scroll.allow_vertical_scroll:
                errors.append("vertical scroll not enabled with many groups")
            if scroll.max_scroll_y <= 0:
                errors.append(
                    f"max_scroll_y={scroll.max_scroll_y}, expected >0"
                )

            self.exit()

    TallApp().run(headless=True, size=(80, 20))

    # --- Report ---
    if verbose:
        for key, val in results.items():
            console.print(f"  {key}: {val}")

    return len(errors) == 0, errors, results


def verify_pane_no_default(verbose: bool = False) -> bool:
    """Verify ProjectStatePane starts with no active section."""
    from textual.app import App, ComposeResult
    from toad.widgets.project_state_pane import (
        ProjectStatePane,
        SECTION_PLANNING,
        SECTION_STATE,
    )

    errors: list[str] = []
    results: dict[str, object] = {}

    class TestApp(App):
        CSS = """
        Screen { overflow: hidden; }
        ProjectStatePane { display: block; width: 100%; }
        """

        def compose(self) -> ComposeResult:
            yield ProjectStatePane(id="psp")

        def on_mount(self) -> None:
            self.set_timer(1.0, self._check)

        def _check(self) -> None:
            pane = self.query_one("#psp", ProjectStatePane)
            planning = pane.query_one(f"#{SECTION_PLANNING}")
            state = pane.query_one(f"#{SECTION_STATE}")

            results["planning_visible"] = planning.display
            results["state_visible"] = state.display

            if planning.display:
                errors.append(
                    "Planning section visible on mount (should be hidden)"
                )
            if state.display:
                errors.append(
                    "State section visible on mount (should be hidden)"
                )

            self.exit()

    TestApp().run(headless=True, size=(80, 30))

    if verbose:
        for key, val in results.items():
            console.print(f"  {key}: {val}")

    return len(errors) == 0, errors, results


def verify_tasks(verbose: bool = False) -> bool:
    """Verify Tasks widget stack: mount + down/enter/escape interaction."""
    from datetime import datetime

    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import ContentSwitcher, DataTable

    from toad.widgets.github_views.task_provider import TaskDetailData, TaskItem
    from toad.widgets.github_views.timeline_provider import ItemStatus, Priority
    from toad.widgets.filter_toolbar import FilterToolbar, filter_tasks
    from toad.widgets.task_detail import TaskDetail
    from toad.widgets.task_table import TaskTable
    from toad.screens.task_detail_screen import TaskDetailScreen

    errors: list[str] = []
    results: dict[str, object] = {}

    tasks = [
        TaskItem(
            id="101",
            number=101,
            title="Wire Tasks tab",
            status=ItemStatus.IN_PROGRESS,
            milestone_id="1",
            milestone_title="M1 — UI",
            priority=Priority.P1,
            assignees=["alberto"],
            effort="2",
            labels=["p1-must-ship"],
            comments_count=4,
            created_at=datetime(2026, 4, 10, 12, 0),
            updated_at=datetime(2026, 4, 15, 9, 0),
            url="https://github.com/acme/proj/issues/101",
        ),
        TaskItem(
            id="102",
            number=102,
            title="Document widgets",
            status=ItemStatus.DONE,
            milestone_id=None,
            milestone_title="",
            priority=Priority.P3,
            assignees=[],
            effort=None,
            labels=["p3"],
            comments_count=0,
            url="https://github.com/acme/proj/issues/102",
        ),
    ]
    details = TaskDetailData(
        number=101,
        body="# body\n\nrendered markdown here.",
        comments_count=2,
        linked_prs=[{"number": 200, "title": "PR"}],
        labels=["p1-must-ship"],
        assignees=["alberto"],
        url="https://github.com/acme/proj/issues/101",
    )

    # --- Test 1: Filter predicate still wired ---
    filtered = filter_tasks(tasks, status=ItemStatus.IN_PROGRESS)
    if [t.number for t in filtered] != [101]:
        errors.append(
            f"filter_tasks: expected [101], got {[t.number for t in filtered]}"
        )

    # --- Test 2: All three widgets mount + interaction flow ---
    class TasksHarness(App[None]):
        CSS = "Screen { overflow: hidden; }"

        def compose(self) -> ComposeResult:
            yield FilterToolbar(id="tb")
            with Horizontal(id="body"):
                yield TaskTable(id="tbl")
                yield TaskDetail(id="detail")

        async def on_mount(self) -> None:
            tbl = self.query_one(TaskTable)
            tbl.set_tasks(tasks)
            tbl.focus()

        def on_data_table_row_selected(
            self, event: DataTable.RowSelected
        ) -> None:
            key = event.row_key.value
            if key is None:
                return
            match = next((t for t in tasks if t.id == str(key)), None)
            if match is not None:
                self.query_one(TaskDetail).show_task(match)

    async def _run_interaction() -> None:
        app = TasksHarness()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            # Confirm all three widgets mounted.
            app.query_one(FilterToolbar)
            tbl = app.query_one(TaskTable)
            detail = app.query_one(TaskDetail)
            switcher = detail.query_one(ContentSwitcher)

            results["row_count"] = tbl.row_count
            results["initial_switcher"] = switcher.current

            if tbl.row_count != len(tasks):
                errors.append(
                    f"table row_count={tbl.row_count}, expected {len(tasks)}"
                )
            if switcher.current != "empty":
                errors.append(
                    f"initial switcher={switcher.current}, expected 'empty'"
                )

            await pilot.press("down", "enter")
            await pilot.pause()
            results["after_enter_switcher"] = switcher.current
            if switcher.current != "detail":
                errors.append(
                    f"after enter switcher={switcher.current}, expected 'detail'"
                )

            # Escape on list screen should be a no-op (no screen pushed).
            await pilot.press("escape")
            await pilot.pause()
            results["after_escape_screen"] = type(app.screen).__name__
            if isinstance(app.screen, TaskDetailScreen):
                errors.append(
                    "escape unexpectedly left TaskDetailScreen active on list"
                )

            # Push + escape round-trip: confirms screen-stack pop works.
            app.push_screen(TaskDetailScreen(tasks[0], details))
            await pilot.pause()
            if not isinstance(app.screen, TaskDetailScreen):
                errors.append("push_screen(TaskDetailScreen) did not activate")
            await pilot.press("escape")
            await pilot.pause()
            results["final_screen"] = type(app.screen).__name__
            if isinstance(app.screen, TaskDetailScreen):
                errors.append(
                    "escape on TaskDetailScreen did not pop back to list"
                )

    asyncio.run(_run_interaction())

    if verbose:
        for key, val in results.items():
            console.print(f"  {key}: {val}")

    return len(errors) == 0, errors, results


def verify_live_data_probe(verbose: bool = False) -> bool:
    """Probe the real GitHub API through TaskProvider.

    Skips gracefully if `gh` is not installed or not authenticated.
    """
    errors: list[str] = []
    results: dict[str, object] = {}

    # Probe `gh auth status` — skip if unauth'd or gh missing.
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        console.print("  [yellow]skipped: no gh auth[/yellow] (gh not installed)")
        return True, [], {"status": "skipped-no-gh"}
    except subprocess.TimeoutExpired:
        console.print("  [yellow]skipped: no gh auth[/yellow] (timeout)")
        return True, [], {"status": "skipped-timeout"}

    if proc.returncode != 0:
        console.print("  [yellow]skipped: no gh auth[/yellow]")
        return True, [], {"status": "skipped-unauth"}

    # Run the fetch.
    from toad.widgets.github_views.task_provider import TaskProvider

    async def _fetch() -> int:
        provider = TaskProvider(
            repo="DEGAorg/claude-code-config", project_number=8
        )
        tasks = await provider.fetch_tasks()
        return len(tasks)

    try:
        count = asyncio.run(_fetch())
        results["task_count"] = count
        if verbose:
            console.print(f"  fetched {count} tasks from live GitHub API")
    except Exception as exc:  # noqa: BLE001 - probe surfaces any parser break
        errors.append(f"live fetch failed: {exc.__class__.__name__}: {exc}")

    return len(errors) == 0, errors, results


def verify_subagents(verbose: bool = False) -> bool:
    """Verify SubagentTabSection: mount hidden, open reveals, close hides."""
    from pathlib import Path
    from unittest.mock import MagicMock

    from textual.app import App, ComposeResult
    from textual.widgets import Static, TabbedContent

    from toad.widgets.subagent_tab_section import SubagentTabSection

    errors: list[str] = []
    results: dict[str, object] = {}

    def _factory(name: str, objective: str):
        return Static(f"{name}: {objective}"), MagicMock()

    async def _run() -> None:
        class Harness(App[None]):
            CSS = "Screen { overflow: hidden; }"

            def compose(self) -> ComposeResult:
                yield SubagentTabSection(
                    project_path=Path("/tmp/verify-subagents"),
                    agent_factory=_factory,
                    id="section-subagents",
                )

        app = Harness()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            section = app.query_one(SubagentTabSection)

            results["initial_display"] = section.display
            results["initial_empty"] = section.is_empty
            if section.display:
                errors.append("section visible on mount (should be hidden)")
            if not section.is_empty:
                errors.append("section non-empty on mount")

            resolved = section.open_tab("Alpha", "do a thing")
            await pilot.pause()
            results["resolved_first"] = resolved
            results["after_open_display"] = section.display
            results["after_open_tabs"] = section.tab_names
            if resolved != "Alpha":
                errors.append(
                    f"first open resolved to {resolved!r}, expected 'Alpha'"
                )
            if not section.display:
                errors.append("section hidden after open_tab")

            dup = section.open_tab("Alpha", "again")
            await pilot.pause()
            results["resolved_dup"] = dup
            if dup != "Alpha 2":
                errors.append(
                    f"duplicate name resolved to {dup!r}, expected 'Alpha 2'"
                )

            tabs = section.query_one("#subagents-tabs", TabbedContent)
            results["pane_count"] = tabs.tab_count
            if tabs.tab_count != 2:
                errors.append(
                    f"TabbedContent has {tabs.tab_count} panes, expected 2"
                )

            section.close_tab("Alpha")
            section.close_tab("Alpha 2")
            await pilot.pause()
            results["after_close_display"] = section.display
            results["after_close_empty"] = section.is_empty
            if section.display:
                errors.append("section still visible after closing all tabs")
            if not section.is_empty:
                errors.append("section non-empty after closing all tabs")

    asyncio.run(_run())

    if verbose:
        for key, val in results.items():
            console.print(f"  {key}: {val}")

    return len(errors) == 0, errors, results


def verify_outreach(verbose: bool = False) -> bool:
    """Verify the Outreach card widgets mount and render.

    Uses synthetic data — does not require the private ``rpa_outreach``
    extension or a live DB. Confirms layout / rendering parity with the
    rest of the pane.
    """
    from textual.app import App, ComposeResult
    from textual.containers import Vertical

    from toad.widgets.outreach_cards import (
        AccountDot,
        Histogram,
        RankedBar,
        StatLine,
    )

    errors: list[str] = []
    results: dict[str, object] = {}

    class OutreachHarness(App[None]):
        CSS = "Screen { overflow: hidden; }"

        def compose(self) -> ComposeResult:
            with Vertical(id="outreach-container"):
                yield StatLine(
                    "Prospects",
                    total=2044,
                    segments=(
                        ("messaged", 845, "success"),
                        ("pending", 1199, "warning"),
                    ),
                    id="stat",
                )
                yield Histogram(
                    "Sends · 24h",
                    buckets=tuple(range(24)),
                    total=276,
                    id="hist",
                )
                yield RankedBar(
                    "Hackathons",
                    rows=(
                        ("Alpha Hack", 12, 50),
                        ("Beta Hack", 40, 80),
                        ("Gamma Hack", 3, 9),
                    ),
                    id="rank",
                )
                yield AccountDot(
                    name="acct-1",
                    active=True,
                    sends_per_hour=12.3,
                    last_sent="5m ago",
                    id="dot",
                )

    async def _run() -> None:
        app = OutreachHarness()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            stat = app.query_one("#stat", StatLine)
            hist = app.query_one("#hist", Histogram)
            rank = app.query_one("#rank", RankedBar)
            dot = app.query_one("#dot", AccountDot)

            results["stat_text"] = stat.rendered.plain[:40]
            results["hist_text"] = hist.rendered.plain[:40]
            results["rank_text"] = rank.rendered.plain[:40]
            results["dot_text"] = dot.rendered.plain

            if "Prospects" not in stat.rendered.plain:
                errors.append("StatLine did not render 'Prospects' label")
            if "2,044" not in stat.rendered.plain:
                errors.append("StatLine did not render total 2,044")
            if "Sends" not in hist.rendered.plain:
                errors.append("Histogram did not render 'Sends' label")
            if "Hackathons" not in rank.rendered.plain:
                errors.append("RankedBar did not render 'Hackathons' label")
            if "acct-1" not in dot.rendered.plain:
                errors.append("AccountDot did not render account name")

    asyncio.run(_run())

    # Verify discover() returns None when the extension cannot be imported.
    # Cannot gate on env var alone anymore — provider resolves DSN from its
    # own shipped .env too, so "env unset" is not a guaranteed None.
    import sys

    from toad.outreach.registry import discover

    ext_module = "toad.extensions.rpa_outreach"
    saved_module = sys.modules.pop(ext_module, None)
    saved_rpa = sys.modules.pop(f"{ext_module}.rpa_outreach", None)
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __builtins__["__import__"]  # type: ignore[index]

    def _block_import(name: str, *a: object, **kw: object) -> object:
        if name == ext_module or name.startswith(ext_module + "."):
            raise ImportError(f"simulated missing submodule: {name}")
        return real_import(name, *a, **kw)  # type: ignore[misc]

    import builtins

    builtins.__import__ = _block_import  # type: ignore[assignment]
    try:
        provider = discover()
        results["discover_none_when_module_absent"] = provider is None
        if provider is not None:
            errors.append("discover() returned non-None with submodule blocked")
    finally:
        builtins.__import__ = real_import  # type: ignore[assignment]
        if saved_module is not None:
            sys.modules[ext_module] = saved_module
        if saved_rpa is not None:
            sys.modules[f"{ext_module}.rpa_outreach"] = saved_rpa

    if verbose:
        for key, val in results.items():
            console.print(f"  {key}: {val}")

    return len(errors) == 0, errors, results


def verify_plan_execution(verbose: bool = False) -> bool:
    """Verify ProjectStatePane auto-opens a plan tab from master.json.

    Writes a fixture project containing ``.orchestrator/master.json`` plus
    one plan dir, mounts ``ProjectStatePane``, registers a stub model
    factory, and asserts the pane reveals itself, the plan tab is
    mounted under the expected id, and the status rail renders one glyph
    per plan item with the correct running glyph.
    """
    import json
    import tempfile
    from pathlib import Path
    from typing import Any

    from textual.app import App, ComposeResult

    from toad.data.plan_execution_model import PlanExecutionModel
    from toad.widgets.plan_execution_section import PlanExecutionSection
    from toad.widgets.plan_execution_tab import PlanExecutionTab
    from toad.widgets.plan_status_rail import STATUS_GLYPHS, PlanStatusRail
    from toad.widgets.project_state_pane import ProjectStatePane

    class _LateTarget:
        """Proxies ``post_message`` to a real widget bound after mount."""

        def __init__(self) -> None:
            self.target: Any = None

        def post_message(self, message: Any) -> bool:
            if self.target is None:
                return False
            return bool(self.target.post_message(message))

    late_target = _LateTarget()
    built_models: list[PlanExecutionModel] = []

    errors: list[str] = []
    results: dict[str, object] = {}

    SLUG = "20260427-smoke"

    def _state_payload(status: str) -> dict[str, object]:
        return {
            "version": 1,
            "plan": SLUG,
            "issueNumber": 99,
            "items": [
                {
                    "id": 1,
                    "description": "task",
                    "deps": [],
                    "status": status,
                }
            ],
        }

    def _write_state(plans_dir: Path, status: str) -> None:
        (plans_dir / "state.json").write_text(
            json.dumps(_state_payload(status)), encoding="utf-8"
        )

    def _write_fixture(project: Path) -> None:
        plans_dir = project / ".orchestrator" / "plans" / SLUG
        (plans_dir / "logs").mkdir(parents=True)
        _write_state(plans_dir, "running")
        state_path = plans_dir / "state.json"
        (project / ".orchestrator" / "master.json").write_text(
            json.dumps(
                {
                    "plans": [
                        {
                            "slug": SLUG,
                            "status": "running",
                            "statePath": str(state_path),
                            "startedAt": "2026-04-27T12:00:00Z",
                            "updatedAt": "2026-04-27T12:00:00Z",
                            "progress": {
                                "total": 1,
                                "done": 0,
                                "running": 1,
                                "failed": 0,
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            _write_fixture(project)
            plans_dir = project / ".orchestrator" / "plans" / SLUG

            class Harness(App[None]):
                CSS = "Screen { overflow: hidden; }"

                def compose(self) -> ComposeResult:
                    yield ProjectStatePane(project_path=project)

            app = Harness()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                pane = app.query_one(ProjectStatePane)

                def _factory(slug: str) -> PlanExecutionModel | None:
                    plan_dir = project / ".orchestrator" / "plans" / slug
                    if not plan_dir.is_dir():
                        return None
                    model = PlanExecutionModel(plan_dir, target=late_target)
                    model.start()
                    built_models.append(model)
                    return model

                pane.configure_plan_execution(_factory)
                await pilot.pause()
                await pilot.pause()

                results["pane_display"] = pane.display
                if not pane.display:
                    errors.append(
                        "ProjectStatePane.display is False after configure_plan_execution"
                    )

                section = pane.query_one(PlanExecutionSection)
                results["section_display"] = section.display
                results["open_slugs"] = sorted(section.open_slugs)
                if not section.display:
                    errors.append("PlanExecutionSection hidden after bootstrap")
                if SLUG not in section.open_slugs:
                    errors.append(
                        f"slug {SLUG!r} missing from open_slugs={section.open_slugs}"
                    )

                tabs = pane.query(PlanExecutionTab)
                results["tab_count"] = len(tabs)
                if len(tabs) != 1:
                    errors.append(
                        f"expected 1 PlanExecutionTab, found {len(tabs)}"
                    )
                else:
                    tab = tabs.first()
                    results["tab_id"] = tab.id
                    expected_id = f"plan-tab-{SLUG}"
                    if tab.id != expected_id:
                        errors.append(
                            f"tab id={tab.id!r}, expected {expected_id!r}"
                        )
                    # Bind the late target so model messages reach the tab.
                    late_target.target = tab

                rails = pane.query(PlanStatusRail)
                if len(rails) != 1:
                    errors.append(
                        f"expected 1 PlanStatusRail, found {len(rails)}"
                    )
                else:
                    rail = rails.first()
                    glyphs = rail.glyphs_plain()
                    results["rail_glyphs"] = glyphs
                    results["rail_verdict"] = rail.verdict_label()
                    if len(glyphs) != 1:
                        errors.append(
                            f"status rail glyph count={len(glyphs)}, expected 1"
                        )
                    elif glyphs[0] != STATUS_GLYPHS["running"]:
                        errors.append(
                            f"glyph={glyphs[0]!r}, expected running "
                            f"{STATUS_GLYPHS['running']!r}"
                        )
                    if rail.verdict_label() != "running":
                        errors.append(
                            f"verdict={rail.verdict_label()!r}, expected 'running'"
                        )

                    # Mutate state.json — backstop interval (or watcher
                    # event) should drive an ItemStatusChanged through to
                    # the rail.
                    _write_state(plans_dir, "done")
                    await pilot.pause(3.0)

                    glyphs_after = rail.glyphs_plain()
                    results["rail_glyphs_after_mutation"] = glyphs_after
                    if len(glyphs_after) != 1:
                        errors.append(
                            f"after mutation glyph count={len(glyphs_after)}, "
                            f"expected 1"
                        )
                    elif glyphs_after[0] != STATUS_GLYPHS["done"]:
                        errors.append(
                            f"after mutation glyph={glyphs_after[0]!r}, "
                            f"expected done {STATUS_GLYPHS['done']!r}"
                        )

    asyncio.run(_run())

    if verbose:
        for key, val in results.items():
            console.print(f"  {key}: {val}")

    return len(errors) == 0, errors, results


def verify_imports(verbose: bool = False) -> bool:
    """Verify all key modules import without error."""
    errors: list[str] = []
    modules = [
        "toad.widgets.gantt_timeline",
        "toad.widgets.project_state_pane",
        "toad.widgets.github_state",
        "toad.widgets.github_views.fetch",
        "toad.widgets.github_views.timeline_provider",
        "toad.widgets.github_views.github_timeline_provider",
        "toad.widgets.github_views.timeline_data",
        "toad.widgets.github_views.task_provider",
        "toad.widgets.task_table",
        "toad.widgets.task_detail",
        "toad.widgets.filter_toolbar",
        "toad.screens.task_detail_screen",
        "toad.widgets.subagent_tab_section",
        "toad.outreach.protocol",
        "toad.outreach.registry",
        "toad.widgets.outreach_cards",
        "toad.widgets.plan_dep_graph",
        "toad.widgets.plan_status_rail",
        "toad.widgets.plan_worker_log_pane",
        "toad.widgets.plan_execution_tab",
        "toad.widgets.plan_execution_section",
    ]
    for mod in modules:
        try:
            __import__(mod)
        except Exception as exc:
            errors.append(f"{mod}: {exc}")

    return len(errors) == 0, errors, {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify TUI widgets")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--widget",
        choices=[
            "gantt",
            "imports",
            "pane",
            "tasks",
            "subagents",
            "outreach",
            "plan-execution",
            "live",
            "all",
        ],
        default="all",
    )
    args = parser.parse_args()

    checks = {
        "imports": verify_imports,
        "gantt": verify_gantt,
        "pane": verify_pane_no_default,
        "tasks": verify_tasks,
        "subagents": verify_subagents,
        "outreach": verify_outreach,
        "plan-execution": verify_plan_execution,
    }
    # Live probe only runs when explicitly requested — it hits the network.
    if args.widget == "live":
        checks = {"live": verify_live_data_probe}
    elif args.widget != "all":
        checks = {args.widget: checks[args.widget]}

    all_passed = True
    for name, check_fn in checks.items():
        console.print(f"\n[bold]Checking {name}...[/bold]")
        passed, errors, _results = check_fn(verbose=args.verbose)
        if passed:
            console.print("  [green]PASS[/green]")
        else:
            all_passed = False
            for err in errors:
                console.print(f"  [red]FAIL[/red]: {err}")

    if all_passed:
        console.print("\n[bold green]All checks passed.[/bold green]")
    else:
        console.print("\n[bold red]Some checks failed.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
