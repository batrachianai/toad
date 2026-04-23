"""Right-side pane for project state — dynamic N-section layout."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.timer import Timer
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Static,
    TabbedContent,
    TabPane,
)

from toad.widgets.builder_view import BuilderView
from toad.widgets.canon_state import CanonStateWidget
from toad.widgets.filter_toolbar import FilterToolbar, FilterState, filter_tasks
from toad.widgets.gantt_timeline import GanttTimeline
from toad.widgets.github_views.github_timeline_provider import (
    GitHubTimelineProvider,
)
from toad.widgets.github_views.task_provider import TaskItem, TaskProvider
from toad.widgets.github_views.timeline_data import build_timeline
from toad.widgets.plan import Plan
from toad.widgets.project_directory_tree import ProjectDirectoryTree
from toad.widgets.task_detail import TaskDetail
from toad.widgets.task_table import TaskTable

log = logging.getLogger(__name__)


def _read_timeline_config(
    project_path: Path,
) -> dict[str, Any] | None:
    """Read timeline config from dega-core.yaml.

    Returns:
        Dict with ``repo`` and ``project_number`` keys, or None.
    """
    config_path = project_path / "dega-core.yaml"
    if not config_path.exists():
        return None
    try:
        config = yaml.safe_load(config_path.read_text("utf-8"))
        tl = config.get("timeline", {})
        repo = tl.get("repo")
        project_number = tl.get("project_number")
        if repo and project_number is not None:
            return {
                "repo": str(repo),
                "project_number": int(project_number),
            }
    except Exception as exc:
        log.warning("Failed to read timeline config: %s", exc)
    return None


# Section IDs — used as TabbedContent widget IDs and toolbar button suffix
SECTION_CONTEXT = "section-context"
SECTION_PLANNING = "section-planning"
SECTION_STATE = "section-state"


@dataclass
class _SectionDef:
    """Definition of a pane section."""

    section_id: str
    button_label: str


# Ordered list of sections — add new ones here
SECTIONS: list[_SectionDef] = [
    _SectionDef(SECTION_CONTEXT, "Context"),
    _SectionDef(SECTION_PLANNING, "Planning"),
    _SectionDef(SECTION_STATE, "State"),
]


# Panel routing registry.
#
# Maps an agent-facing panel ID (used in ACP ``open_panel`` messages) to a
# ``(section_id, tab_id)`` pair. Aliases pointing at the same tab are allowed
# — the agent prompt can refer to the panel by any of them. To add a new
# panel: add the tab in ``compose`` and register its alias(es) here.
PANEL_ROUTES: dict[str, tuple[str, str]] = {
    "context": (SECTION_CONTEXT, "tab-plan"),
    "plan": (SECTION_CONTEXT, "tab-plan"),
    "files": (SECTION_CONTEXT, "tab-files"),
    "planning": (SECTION_PLANNING, "tab-tasks"),
    "timeline": (SECTION_PLANNING, "tab-timeline"),
    # Board with pre-applied type chip (handled by open_panel routing below).
    "tasks": (SECTION_PLANNING, "tab-tasks"),
    "board": (SECTION_PLANNING, "tab-tasks"),
    "plans": (SECTION_PLANNING, "tab-tasks"),
    "prs": (SECTION_PLANNING, "tab-tasks"),
    "pull_requests": (SECTION_PLANNING, "tab-tasks"),
    "bugs": (SECTION_PLANNING, "tab-tasks"),
    "features": (SECTION_PLANNING, "tab-tasks"),
    "github": (SECTION_PLANNING, "tab-tasks"),
    "status": (SECTION_PLANNING, "tab-tasks"),
    "state": (SECTION_STATE, "tab-builder"),
    "builder": (SECTION_STATE, "tab-builder"),
}


# For panel aliases that imply a type filter, map the alias to the chip value.
PANEL_TYPE_PRESETS: dict[str, str] = {
    "plans": "plan",
    "prs": "pr",
    "pull_requests": "pr",
    "bugs": "bug",
    "features": "feature",
}


# Filter schema: panel ID → list of supported filter keys. Used by the
# agent prompt and documented in the ``canon-panel-routing`` skill.
PANEL_FILTERS: dict[str, tuple[str, ...]] = {
    "tasks": ("status", "milestone", "priority", "title", "type"),
    "board": ("status", "milestone", "priority", "title", "type"),
}


class ProjectStatePane(Vertical):
    """Toggleable right pane with N dynamic sections.

    Each section is a ``TabbedContent`` with ``height: 1fr``.
    All sections start hidden. Visible sections share height
    evenly (1 = 100%, 2 = 50/50, 3 = 33/33/33). When all
    sections are hidden the pane auto-closes.
    """

    class AllSectionsHidden(Message):
        """Posted when every section is hidden — pane should close."""

    BINDINGS = [
        Binding("r", "refresh_tasks", "Refresh tasks", show=False),
        Binding("slash", "focus_task_filter", "Filter tasks", show=False),
        Binding("escape", "tasks_back", "Back to list", show=False),
    ]

    DEFAULT_CSS = """
    ProjectStatePane {
        display: none;
        width: 50%;
        border-left: tall $primary 30%;
    }

    ProjectStatePane #pane-toolbar {
        height: auto;
        dock: top;
        padding: 1 2;
    }

    ProjectStatePane #pane-toolbar Button {
        min-width: 10;
        height: 1;
        margin: 0 1 0 0;
        border: none;
        background: $surface;
        color: $text-muted;
    }

    ProjectStatePane #pane-toolbar Button.active {
        background: $primary 30%;
        color: $text;
        text-style: bold;
    }

    ProjectStatePane .pane-section {
        height: 1fr;
    }

    ProjectStatePane TabPane {
        padding: 0 1;
    }

    ProjectStatePane #tasks-switcher {
        height: 1fr;
    }

    ProjectStatePane #tasks-list-view,
    ProjectStatePane #tasks-detail-view {
        height: 1fr;
    }

    ProjectStatePane #task-table {
        width: 1fr;
        height: 1fr;
    }

    ProjectStatePane #task-detail {
        width: 1fr;
        height: 1fr;
    }

    ProjectStatePane #tasks-breadcrumb {
        height: auto;
        padding: 0 1;
    }

    ProjectStatePane #tasks-back-btn {
        min-width: 12;
        height: 1;
        margin-right: 1;
        border: none;
        background: $primary 30%;
        color: $text;
    }

    ProjectStatePane #tasks-breadcrumb-label {
        color: $text-muted;
        height: 1;
        padding-top: 0;
    }

    ProjectStatePane #tasks-status {
        height: auto;
        min-height: 2;
        padding: 1 2;
        margin: 0 1;
        background: $primary 20%;
        color: $text;
        text-style: bold;
        border-left: thick $primary;
    }

    ProjectStatePane #tasks-status.error {
        background: $error 25%;
        color: $text;
        text-style: bold;
        border-left: thick $error;
    }

    ProjectStatePane .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2 1;
        text-align: center;
    }
    """

    REFRESH_INTERVAL = 60

    def __init__(
        self,
        project_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._project_path = project_path or Path(".").resolve()
        self._refresh_timer: Timer | None = None
        self._tasks_refresh_timer: Timer | None = None
        self._provider = self._make_provider()
        self._task_provider = self._make_task_provider()
        self._all_tasks: list[TaskItem] = []
        self._filter_state = FilterState()
        self._selected_task_id: str | None = None
        self._stack_mode: bool = False

    def compose(self) -> ComposeResult:
        # Toolbar: one button per section + a stack-mode toggle
        with Horizontal(id="pane-toolbar"):
            for sec in SECTIONS:
                yield Button(
                    sec.button_label,
                    id=f"btn-{sec.section_id}",
                )
            yield Button(
                "⊟",
                id="btn-stack-toggle",
                tooltip="Show multiple sections at once (click a section button in this mode to toggle it)",
            )

        # --- Context section (plan + files) ---
        with TabbedContent(id=SECTION_CONTEXT, classes="pane-section"):
            with TabPane("Plan", id="tab-plan"):
                yield Plan([], id="pane-plan")
            with TabPane("Files", id="tab-files"):
                yield ProjectDirectoryTree(
                    self._project_path,
                    id="project_directory_tree",
                )

        # --- Planning section: Board / Timeline.
        # Plans and PRs are now chip filters on the Board, not separate tabs.
        with TabbedContent(id=SECTION_PLANNING, classes="pane-section"):
            with TabPane("Board", id="tab-tasks"):
                with ContentSwitcher(initial="tasks-list-view", id="tasks-switcher"):
                    with Vertical(id="tasks-list-view"):
                        yield FilterToolbar(id="task-filter-toolbar")
                        yield Static("", id="tasks-status")
                        yield TaskTable(id="task-table")
                    with Vertical(id="tasks-detail-view"):
                        with Horizontal(id="tasks-breadcrumb"):
                            yield Button(
                                "← Back",
                                id="tasks-back-btn",
                                tooltip="Return to the task list (Esc)",
                            )
                            yield Static(
                                "",
                                id="tasks-breadcrumb-label",
                            )
                        yield TaskDetail(id="task-detail")
            with TabPane("Timeline", id="tab-timeline"):
                yield GanttTimeline(id="pane-gantt")

        # Canon state watcher (invisible, drives State view)
        yield CanonStateWidget(
            project_path=self._project_path,
            id="canon-state",
        )

        # --- State section (canon build + run) ---
        with TabbedContent(id=SECTION_STATE, classes="pane-section"):
            with TabPane("State", id="tab-builder"):
                yield BuilderView(id="builder-view")

    def on_mount(self) -> None:
        # All sections start hidden; the user opens one via toolbar / chat.
        self.query_one(f"#{SECTION_CONTEXT}").display = False
        self.query_one(f"#{SECTION_PLANNING}").display = False
        self.query_one(f"#{SECTION_STATE}").display = False
        self._sync_toolbar()
        self._fetch_timeline()
        self._fetch_tasks()

    def watch_display(self, visible: bool) -> None:
        """Stop timers when entire pane is hidden."""
        if not visible:
            self._stop_timeline_timer()
            self._stop_tasks_timer()

    def _sync_timeline_timer(self, section_id: str, *, visible: bool) -> None:
        """Start/stop the timeline refresh timer when the Planning section toggles."""
        if section_id != SECTION_PLANNING:
            return
        if visible:
            self._fetch_timeline()
            if self._refresh_timer is None:
                self._refresh_timer = self.set_interval(
                    self.REFRESH_INTERVAL, self._fetch_timeline
                )
        else:
            self._stop_timeline_timer()

    def _stop_timeline_timer(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

    @on(TabbedContent.TabActivated, f"#{SECTION_PLANNING}")
    def _on_planning_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        active = event.tabbed_content.active
        if active == "tab-tasks":
            self._fetch_tasks()
            self._start_tasks_timer()
        else:
            self._stop_tasks_timer()

    # ------------------------------------------------------------------
    # Toolbar — generic button handler
    # ------------------------------------------------------------------

    @on(Button.Pressed)
    def _on_toolbar_button(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "btn-stack-toggle":
            event.stop()
            self._stack_mode = not self._stack_mode
            self._sync_toolbar()
            return
        if not btn_id.startswith("btn-section-"):
            return
        event.stop()
        section_id = btn_id.removeprefix("btn-")
        if self._stack_mode:
            # Multi-select mode — toggle the single section
            self.toggle_section(section_id)
        else:
            # Default accordion mode — show only the clicked section
            self.show_single_section(section_id)

    def _sync_toolbar(self) -> None:
        """Sync all toolbar buttons and fire AllSectionsHidden if needed."""
        any_visible = False
        for sec in SECTIONS:
            widget = self.query_one(f"#{sec.section_id}")
            btn = self.query_one(f"#btn-{sec.section_id}", Button)
            if widget.display:
                btn.add_class("active")
                any_visible = True
            else:
                btn.remove_class("active")
        # Stack-mode toggle visual state
        try:
            stack_btn = self.query_one("#btn-stack-toggle", Button)
        except NoMatches:
            stack_btn = None
        if stack_btn is not None:
            if self._stack_mode:
                stack_btn.add_class("active")
                stack_btn.tooltip = (
                    "Multi-section mode ON — click again for single-section"
                )
            else:
                stack_btn.remove_class("active")
                stack_btn.tooltip = (
                    "Show multiple sections at once (accordion mode is on)"
                )
        if not any_visible:
            self.post_message(self.AllSectionsHidden())

    # ------------------------------------------------------------------
    # Public API — section visibility
    # ------------------------------------------------------------------

    def show_section(self, section_id: str) -> None:
        """Show a section by its ID."""
        self.query_one(f"#{section_id}").display = True
        self._sync_toolbar()
        self._sync_timeline_timer(section_id, visible=True)

    def show_single_section(self, section_id: str) -> None:
        """Show ``section_id`` and hide all other sections (accordion)."""
        for sec in SECTIONS:
            visible = sec.section_id == section_id
            widget = self.query_one(f"#{sec.section_id}")
            widget.display = visible
            self._sync_timeline_timer(sec.section_id, visible=visible)
        self._sync_toolbar()

    def hide_section(self, section_id: str) -> None:
        """Hide a section by its ID."""
        self.query_one(f"#{section_id}").display = False
        self._sync_toolbar()
        self._sync_timeline_timer(section_id, visible=False)

    def toggle_section(self, section_id: str) -> None:
        """Toggle a section's visibility."""
        widget = self.query_one(f"#{section_id}")
        widget.display = not widget.display
        self._sync_toolbar()
        self._sync_timeline_timer(section_id, visible=widget.display)

    def hide_all_sections(self) -> None:
        """Hide every section."""
        for sec in SECTIONS:
            self.query_one(f"#{sec.section_id}").display = False
        self._sync_toolbar()

    # ------------------------------------------------------------------
    # Public API — tab activation
    # ------------------------------------------------------------------

    def activate_tab(self, tab_id: str) -> None:
        """Switch to a specific tab by its pane id."""
        for tc in self.query(TabbedContent):
            try:
                tc.query_one(f"#{tab_id}", TabPane)
            except Exception:
                continue
            tc.active = tab_id
            return
        log.warning("Tab %r not found in ProjectStatePane", tab_id)

    # ------------------------------------------------------------------
    # Provider setup
    # ------------------------------------------------------------------

    def _make_provider(self) -> GitHubTimelineProvider | None:
        """Create a provider from dega-core.yaml config."""
        cfg = _read_timeline_config(self._project_path)
        if cfg is None:
            log.warning("No timeline config in dega-core.yaml")
            return None
        return GitHubTimelineProvider(
            repo=cfg["repo"],
            project_number=cfg["project_number"],
        )

    # ------------------------------------------------------------------
    # Timeline fetch — async provider pipeline
    # ------------------------------------------------------------------

    @work(exclusive=True, exit_on_error=False)
    async def _fetch_timeline(self) -> None:
        """Fetch timeline via provider, transform, and update widget."""
        if self._provider is None:
            return
        try:
            milestones = await self._provider.fetch_milestones()
            items = await self._provider.fetch_items()
            timeline = build_timeline(milestones, items)
            gantt = self.query_one("#pane-gantt", GanttTimeline)
            gantt.timeline_data = timeline
        except Exception as exc:
            log.warning("Timeline fetch failed: %s", exc)

    def refresh_timeline(self) -> None:
        """Re-fetch timeline data. Called via socket controller."""
        self._fetch_timeline()

    # ------------------------------------------------------------------
    # Tasks — provider → filter → table → detail
    # ------------------------------------------------------------------

    def _make_task_provider(self) -> TaskProvider | None:
        cfg = _read_timeline_config(self._project_path)
        if cfg is None:
            return None
        return TaskProvider(
            repo=cfg["repo"],
            project_number=cfg["project_number"],
        )

    @work(exclusive=True, exit_on_error=False, group="fetch-tasks")
    async def _fetch_tasks(self) -> None:
        if self._task_provider is None:
            self._set_tasks_status("No task provider configured.", error=True)
            return
        self._set_tasks_status("Loading tasks…")
        try:
            tasks = await self._task_provider.fetch_tasks()
        except Exception as exc:
            log.warning("Task fetch failed: %s", exc)
            self._set_tasks_status(f"Task fetch failed: {exc}", error=True)
            return
        self._all_tasks = tasks
        self._sync_milestone_options(tasks)
        self._apply_filters()

    def _set_tasks_status(self, message: str, *, error: bool = False) -> None:
        """Update the inline status label above the table."""
        try:
            label = self.query_one("#tasks-status", Static)
        except NoMatches:
            return
        label.update(message)
        if error:
            label.add_class("error")
        else:
            label.remove_class("error")

    def _sync_milestone_options(self, tasks: list[TaskItem]) -> None:
        seen: dict[str, str] = {}
        for task in tasks:
            if task.milestone_id and task.milestone_id not in seen:
                seen[task.milestone_id] = task.milestone_title or task.milestone_id
        try:
            toolbar = self.query_one("#task-filter-toolbar", FilterToolbar)
        except NoMatches:
            return
        toolbar.set_milestones([(title, mid) for mid, title in seen.items()])

    def _apply_filters(self) -> None:
        filtered = filter_tasks(
            self._all_tasks,
            status=self._filter_state.status,
            milestone_id=self._filter_state.milestone_id,
            priority=self._filter_state.priority,
            title_query=self._filter_state.title_query,
            type_filter=self._filter_state.type_filter,
            exclude_done=self._filter_state.exclude_done,
        )
        try:
            table = self.query_one("#task-table", TaskTable)
        except NoMatches:
            return
        table.set_column_set(self._filter_state.type_filter or "all")
        table.set_tasks(filtered)
        total = len(self._all_tasks)
        shown = len(filtered)
        if total == 0:
            self._set_tasks_status("No tasks loaded.")
        elif shown == 0:
            self._set_tasks_status(
                f"No tasks match filters ({total} total). Press r to refresh."
            )
        else:
            self._set_tasks_status(
                f"Showing {shown} of {total} tasks."
            )

    @on(FilterToolbar.FiltersChanged)
    def _on_filters_changed(self, event: FilterToolbar.FiltersChanged) -> None:
        event.stop()
        self._filter_state = event.state
        self._apply_filters()

    @on(FilterToolbar.RefreshRequested)
    def _on_tasks_refresh_requested(
        self, event: FilterToolbar.RefreshRequested
    ) -> None:
        event.stop()
        self._fetch_tasks()

    @on(TaskDetail.DrillDownRequested)
    def _on_task_drill_down(self, event: TaskDetail.DrillDownRequested) -> None:
        event.stop()
        self.open_task_drill_down(event.task)

    @on(DataTable.RowSelected, "#task-table")
    def _on_task_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        key = event.row_key.value
        if key is None:
            return
        table = self.query_one("#task-table", TaskTable)
        task = table.get_task(str(key))
        if task is None:
            return
        detail = self.query_one("#task-detail", TaskDetail)
        detail.show_task(task)
        self._selected_task_id = task.id
        self._show_tasks_detail(task)
        self._fetch_task_details(task.number)

    def _show_tasks_detail(self, task: TaskItem) -> None:
        """Switch the Tasks tab to the detail view and update the breadcrumb."""
        try:
            switcher = self.query_one("#tasks-switcher", ContentSwitcher)
            label = self.query_one("#tasks-breadcrumb-label", Static)
        except NoMatches:
            return
        label.update(f"  Board  ›  #{task.number} {task.title}")
        switcher.current = "tasks-detail-view"

    def _show_tasks_list(self) -> None:
        """Switch back to the list view and restore focus on the table."""
        try:
            switcher = self.query_one("#tasks-switcher", ContentSwitcher)
            table = self.query_one("#task-table", TaskTable)
        except NoMatches:
            return
        switcher.current = "tasks-list-view"
        table.focus()

    @on(Button.Pressed, "#tasks-back-btn")
    def _on_tasks_back(self, event: Button.Pressed) -> None:
        event.stop()
        self._show_tasks_list()

    @work(exclusive=True, exit_on_error=False, group="fetch-task-details")
    async def _fetch_task_details(self, number: int) -> None:
        if self._task_provider is None:
            return
        try:
            details = await self._task_provider.fetch_task_details(number)
        except Exception as exc:
            log.warning("Task detail fetch failed for #%s: %s", number, exc)
            return
        try:
            detail = self.query_one("#task-detail", TaskDetail)
        except NoMatches:
            return
        detail.show_details(details)

    def _start_tasks_timer(self) -> None:
        if self._tasks_refresh_timer is None:
            self._tasks_refresh_timer = self.set_interval(
                self.REFRESH_INTERVAL, self._fetch_tasks
            )

    def _stop_tasks_timer(self) -> None:
        if self._tasks_refresh_timer is not None:
            self._tasks_refresh_timer.stop()
            self._tasks_refresh_timer = None

    # ------------------------------------------------------------------
    # Keybindings — active only while the Tasks tab is visible
    # ------------------------------------------------------------------

    def _is_tasks_tab_active(self) -> bool:
        try:
            tc = self.query_one(f"#{SECTION_PLANNING}", TabbedContent)
        except NoMatches:
            return False
        return tc.display and tc.active == "tab-tasks"

    def action_refresh_tasks(self) -> None:
        if not self._is_tasks_tab_active():
            return
        self._fetch_tasks()

    def action_focus_task_filter(self) -> None:
        if not self._is_tasks_tab_active():
            return
        try:
            toolbar = self.query_one("#task-filter-toolbar", FilterToolbar)
        except NoMatches:
            return
        toolbar.focus_title_input()

    def apply_task_filters(self, filters: dict[str, Any] | None) -> None:
        """Apply chat-supplied filters to the Board / Tasks view.

        Recognised keys (all optional): ``status``, ``milestone``, ``priority``,
        ``title``. Invalid values are ignored. Missing keys keep the existing
        selection.
        """
        if not filters:
            return
        from toad.widgets.github_views.timeline_provider import (
            ItemStatus as _Status,
            Priority as _Prio,
        )

        state = self._filter_state
        status = state.status
        milestone_id = state.milestone_id
        priority = state.priority
        title_query = state.title_query

        raw_status = filters.get("status")
        if isinstance(raw_status, str):
            try:
                status = _Status(raw_status.lower())
            except ValueError:
                log.debug("unknown status filter: %s", raw_status)
        raw_priority = filters.get("priority")
        if raw_priority is not None:
            try:
                priority = _Prio(int(str(raw_priority).lstrip("pP")))
            except (ValueError, TypeError):
                log.debug("unknown priority filter: %s", raw_priority)
        raw_milestone = filters.get("milestone")
        if isinstance(raw_milestone, str) and raw_milestone:
            milestone_id = raw_milestone
        raw_title = filters.get("title")
        if isinstance(raw_title, str):
            title_query = raw_title or None
        type_filter = state.type_filter
        raw_type = filters.get("type")
        if isinstance(raw_type, str):
            normalized = raw_type.strip().lower()
            type_filter = None if normalized in ("", "all") else normalized

        self._filter_state = FilterState(
            status=status,
            milestone_id=milestone_id,
            priority=priority,
            title_query=title_query,
            type_filter=type_filter,
            # An explicit status from chat overrides the default hide-done.
            exclude_done=state.exclude_done if status is None else False,
        )
        # Reflect the applied type in the chip UI so the active state matches.
        try:
            toolbar = self.query_one("#task-filter-toolbar", FilterToolbar)
        except NoMatches:
            pass
        else:
            toolbar.set_active_type(type_filter or "all")
        self._apply_filters()

    def action_tasks_back(self) -> None:
        """Pop the detail view if active, else no-op."""
        if not self._is_tasks_tab_active():
            return
        try:
            switcher = self.query_one("#tasks-switcher", ContentSwitcher)
        except NoMatches:
            return
        if switcher.current == "tasks-detail-view":
            self._show_tasks_list()

    # ------------------------------------------------------------------
    # Drill-down — live-updating screen with lazy details
    # ------------------------------------------------------------------

    def open_task_drill_down(self, task: TaskItem) -> None:
        """Push the full-screen task detail, fetching details into it live."""
        # Lazy import — avoids cycle with ``toad.screens``.
        from toad.screens.task_detail_screen import TaskDetailScreen

        screen = TaskDetailScreen(task)
        self.app.push_screen(screen)
        self._fetch_task_details_into(task.number, screen)

    @work(exclusive=True, exit_on_error=False, group="fetch-drill-details")
    async def _fetch_task_details_into(
        self,
        number: int,
        screen: Any,
    ) -> None:
        if self._task_provider is None:
            return
        try:
            details = await self._task_provider.fetch_task_details(number)
        except Exception as exc:
            log.warning("Drill-down detail fetch failed for #%s: %s", number, exc)
            screen.set_error(str(exc))
            return
        screen.set_details(details)
