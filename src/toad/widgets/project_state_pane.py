"""Right-side pane for project state (timeline, GitHub, orchestrator)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.timer import Timer
from textual.widgets import TabbedContent, TabPane

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


class ProjectStatePane(Vertical):
    """Toggleable right pane with tabbed project state sections.

    Top section (always visible): Timeline + GitHub tabs.
    Bottom section (hidden by default): Plans + Workers tabs.
    Both sections use ``height: 1fr`` so a single visible section
    fills the pane and two visible sections split 50/50.
    """

    class OrchestratorSectionShown(Message):
        """Posted when the orchestrator (bottom) section becomes visible."""

    DEFAULT_CSS = """
    ProjectStatePane {
        display: none;
        width: 50%;
        border-left: tall $primary 30%;
    }

    ProjectStatePane #top-section {
        height: 1fr;
    }

    ProjectStatePane #bottom-section {
        height: 1fr;
        display: none;
    }

    ProjectStatePane #bottom-section.visible {
        display: block;
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
        with TabbedContent(id="top-section"):
            with TabPane("Timeline", id="tab-timeline"):
                yield GanttTimeline(id="pane-gantt")
            with TabPane("GitHub", id="tab-github"):
                yield GitHubStateWidget(
                    project_path=str(self._project_path),
                    id="github_state",
                )

        yield OrchestratorStateWidget(
            project_path=self._project_path,
            id="orchestrator-state",
        )

        with TabbedContent(id="bottom-section"):
            with TabPane("Plans", id="tab-plans"):
                yield PlanListView(id="plan-list-view")
            with TabPane("Workers", id="tab-workers"):
                yield WorkerListView(id="worker-list-view")

    def on_mount(self) -> None:
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
    # Public API
    # ------------------------------------------------------------------

    def activate_tab(self, tab_id: str) -> None:
        """Switch to a specific tab by its pane id.

        ``tab_id`` should be one of: ``tab-timeline``, ``tab-github``,
        ``tab-plans``, ``tab-workers``.
        """
        for tc in self.query(TabbedContent):
            try:
                pane = tc.query_one(f"#{tab_id}", TabPane)
            except Exception:
                continue
            tc.active = tab_id
            pane.focus()
            return
        log.warning("Tab %r not found in ProjectStatePane", tab_id)

    def show_orchestrator_section(self) -> None:
        """Make the bottom orchestrator section visible."""
        bottom = self.query_one("#bottom-section", TabbedContent)
        if not bottom.has_class("visible"):
            bottom.add_class("visible")
            self.post_message(self.OrchestratorSectionShown())

    def on_plan_list_view_plan_selected(
        self, event: PlanListView.PlanSelected
    ) -> None:
        """Forward plan selection to OrchestratorStateWidget."""
        orch = self.query_one(
            "#orchestrator-state", OrchestratorStateWidget
        )
        orch.select_plan(event.slug)

    def hide_orchestrator_section(self) -> None:
        """Hide the bottom orchestrator section."""
        bottom = self.query_one("#bottom-section", TabbedContent)
        bottom.remove_class("visible")

    # ------------------------------------------------------------------
    # Timeline fetch (preserved from original)
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

    def refresh_timeline(self) -> None:
        """Re-fetch timeline data. Called via socket controller."""
        self._fetch_timeline()
