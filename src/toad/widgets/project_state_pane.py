"""Right-side pane for project state — dynamic N-section layout."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Button, TabbedContent, TabPane

from toad.widgets.automation_view import AutomationView
from toad.widgets.builder_view import BuilderView
from toad.widgets.canon_state import CanonStateWidget
from toad.widgets.gantt_timeline import GanttTimeline
from toad.widgets.github_state import GitHubStateWidget
from toad.widgets.orchestrator_state import OrchestratorStateWidget
from toad.widgets.plan_list_view import PlanListView
from toad.widgets.worker_list_view import WorkerListView

log = logging.getLogger(__name__)

DEFAULT_TIMELINE_URL = (
    "https://raw.githubusercontent.com/DEGAorg"
    "/claude-code-config/develop/data/timeline.json"
)


def _read_timeline_url(project_path: Path) -> str:
    """Read timeline URL from dega-core.yaml, fallback to default."""
    config_path = project_path / "dega-core.yaml"
    if config_path.exists():
        try:
            import yaml

            config = yaml.safe_load(config_path.read_text("utf-8"))
            tl = config.get("timeline", {})
            repo = tl.get("repo")
            branch = tl.get("branch")
            path = tl.get("path")
            if repo and branch and path:
                return (
                    f"https://raw.githubusercontent.com/{repo}"
                    f"/{branch}/{path}"
                )
        except Exception as exc:
            log.warning("Failed to read dega-core.yaml: %s", exc)
    return DEFAULT_TIMELINE_URL


# Section IDs — used as TabbedContent widget IDs and toolbar button suffix
SECTION_GITHUB = "section-github"
SECTION_ORCHESTRATOR = "section-orchestrator"
SECTION_BUILDER = "section-builder"
SECTION_AUTOMATIONS = "section-automations"


@dataclass
class _SectionDef:
    """Definition of a pane section."""

    section_id: str
    button_label: str


# Ordered list of sections — add new ones here
SECTIONS: list[_SectionDef] = [
    _SectionDef(SECTION_GITHUB, "GitHub"),
    _SectionDef(SECTION_ORCHESTRATOR, "Plans"),
    _SectionDef(SECTION_BUILDER, "Builder"),
    _SectionDef(SECTION_AUTOMATIONS, "Automations"),
]


class ProjectStatePane(Vertical):
    """Toggleable right pane with N dynamic sections.

    Each section is a ``TabbedContent`` with ``height: 1fr``.
    All sections start hidden. Visible sections share height
    evenly (1 = 100%, 2 = 50/50, 3 = 33/33/33). When all
    sections are hidden the pane auto-closes.
    """

    class AllSectionsHidden(Message):
        """Posted when every section is hidden — pane should close."""

    DEFAULT_CSS = """
    ProjectStatePane {
        display: none;
        width: 50%;
        border-left: tall $primary 30%;
    }

    ProjectStatePane #pane-toolbar {
        height: auto;
        dock: top;
        padding: 0 1;
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

    ProjectStatePane #pane-gantt {
        height: 1fr;
    }

    ProjectStatePane TabPane {
        padding: 0 1;
    }

    ProjectStatePane .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2 1;
        text-align: center;
    }
    """

    REFRESH_INTERVAL = 30

    def __init__(
        self,
        project_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._project_path = project_path or Path(".").resolve()
        self._refresh_timer: Timer | None = None
        self._timeline_url = _read_timeline_url(self._project_path)

    def compose(self) -> ComposeResult:
        # Toolbar with one button per section
        with Horizontal(id="pane-toolbar"):
            for sec in SECTIONS:
                yield Button(
                    sec.button_label,
                    id=f"btn-{sec.section_id}",
                )

        # --- GitHub / Timeline section ---
        with TabbedContent(
            id=SECTION_GITHUB, classes="pane-section"
        ):
            with TabPane("GitHub", id="tab-github"):
                yield GitHubStateWidget(
                    project_path=str(self._project_path),
                    id="github_state",
                )
            with TabPane("Timeline", id="tab-timeline"):
                yield GanttTimeline(id="pane-gantt")

        # Orchestrator state watcher (invisible, drives data)
        yield OrchestratorStateWidget(
            project_path=self._project_path,
            id="orchestrator-state",
        )

        # --- Plans / Workers section ---
        with TabbedContent(
            id=SECTION_ORCHESTRATOR, classes="pane-section"
        ):
            with TabPane("Plans", id="tab-plans"):
                yield PlanListView(id="plan-list-view")
            with TabPane("Workers", id="tab-workers"):
                yield WorkerListView(id="worker-list-view")

        # Canon state watcher (invisible, drives builder/automation)
        yield CanonStateWidget(
            project_path=self._project_path,
            id="canon-state",
        )

        # --- Builder section ---
        with TabbedContent(
            id=SECTION_BUILDER, classes="pane-section"
        ):
            with TabPane("Builder", id="tab-builder"):
                yield BuilderView(id="builder-view")

        # --- Automations section ---
        with TabbedContent(
            id=SECTION_AUTOMATIONS, classes="pane-section"
        ):
            with TabPane("Automation", id="tab-automation"):
                yield AutomationView(id="automation-view")

    def on_mount(self) -> None:
        # All sections hidden by default
        for sec in SECTIONS:
            self.query_one(f"#{sec.section_id}").display = False
        self._sync_toolbar()
        self._fetch_timeline()

    def watch_display(self, visible: bool) -> None:
        """Start/stop auto-refresh timer based on visibility."""
        if visible:
            if self._refresh_timer is None:
                self._refresh_timer = self.set_interval(
                    self.REFRESH_INTERVAL, self._fetch_timeline
                )
        else:
            if self._refresh_timer is not None:
                self._refresh_timer.stop()
                self._refresh_timer = None

    # ------------------------------------------------------------------
    # Toolbar — generic button handler
    # ------------------------------------------------------------------

    @on(Button.Pressed)
    def _on_toolbar_button(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if not btn_id.startswith("btn-section-"):
            return
        event.stop()
        section_id = btn_id.removeprefix("btn-")
        self.toggle_section(section_id)

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
        if not any_visible:
            self.post_message(self.AllSectionsHidden())

    # ------------------------------------------------------------------
    # Public API — section visibility
    # ------------------------------------------------------------------

    def show_section(self, section_id: str) -> None:
        """Show a section by its ID."""
        self.query_one(f"#{section_id}").display = True
        self._sync_toolbar()

    def hide_section(self, section_id: str) -> None:
        """Hide a section by its ID."""
        self.query_one(f"#{section_id}").display = False
        self._sync_toolbar()

    def toggle_section(self, section_id: str) -> None:
        """Toggle a section's visibility."""
        widget = self.query_one(f"#{section_id}")
        widget.display = not widget.display
        self._sync_toolbar()

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
    # Plan selection forwarding
    # ------------------------------------------------------------------

    def on_plan_list_view_plan_selected(
        self, event: PlanListView.PlanSelected
    ) -> None:
        """Forward plan selection to OrchestratorStateWidget."""
        orch = self.query_one(
            "#orchestrator-state", OrchestratorStateWidget
        )
        orch.select_plan(event.slug)

    # ------------------------------------------------------------------
    # Timeline fetch
    # ------------------------------------------------------------------

    @work(thread=True, exit_on_error=False)
    def _fetch_timeline(self) -> None:
        """Fetch timeline from remote URL, fallback to local file."""
        data = self._fetch_remote()
        if data is None:
            data = self._load_local()
        if data is not None:
            self.app.call_from_thread(self._apply_data, data)

    def _apply_data(self, data: dict) -> None:
        gantt = self.query_one("#pane-gantt", GanttTimeline)
        gantt.timeline_data = data

    def _fetch_remote(self) -> dict | None:
        try:
            import httpx

            resp = httpx.get(
                self._timeline_url, timeout=5, follow_redirects=True
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            log.warning(
                "Failed to fetch timeline from %s: %s",
                self._timeline_url,
                exc,
            )
            return None

    def _load_local(self) -> dict | None:
        path = self._project_path / "timeline.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to load local timeline: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Canon auto-show logic
    # ------------------------------------------------------------------

    def on_canon_state_widget_canon_state_detected(
        self,
        _event: CanonStateWidget.CanonStateDetected,
    ) -> None:
        """Auto-show Builder or Automation when canon state appears."""
        canon = self.query_one("#canon-state", CanonStateWidget)
        state = canon.state
        if state.is_build_phase:
            self.show_section(SECTION_BUILDER)
        elif state.is_run_phase:
            self.show_section(SECTION_AUTOMATIONS)

    def on_canon_state_widget_canon_state_updated(
        self,
        event: CanonStateWidget.CanonStateUpdated,
    ) -> None:
        """Auto-switch between Builder and Automation on phase change."""
        state = event.state
        builder_visible = self.query_one(
            f"#{SECTION_BUILDER}"
        ).display
        automation_visible = self.query_one(
            f"#{SECTION_AUTOMATIONS}"
        ).display

        if state.is_build_phase and not builder_visible:
            if automation_visible:
                self.hide_section(SECTION_AUTOMATIONS)
            self.show_section(SECTION_BUILDER)
        elif state.is_run_phase and not automation_visible:
            if builder_visible:
                self.hide_section(SECTION_BUILDER)
            self.show_section(SECTION_AUTOMATIONS)

    def refresh_timeline(self) -> None:
        """Re-fetch timeline data. Called via socket controller."""
        self._fetch_timeline()
