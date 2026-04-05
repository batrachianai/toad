"""Right-side pane for project state — dynamic N-section layout."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Button, TabbedContent, TabPane

from toad.widgets.builder_view import BuilderView
from toad.widgets.canon_state import CanonStateWidget
from toad.widgets.gantt_timeline import GanttTimeline
from toad.widgets.github_state import GitHubStateWidget
from toad.widgets.github_views.github_timeline_provider import (
    GitHubTimelineProvider,
)
from toad.widgets.github_views.timeline_data import build_timeline

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
SECTION_GITHUB = "section-github"
SECTION_BUILDER = "section-builder"


@dataclass
class _SectionDef:
    """Definition of a pane section."""

    section_id: str
    button_label: str


# Ordered list of sections — add new ones here
SECTIONS: list[_SectionDef] = [
    _SectionDef(SECTION_BUILDER, "State"),
    _SectionDef(SECTION_GITHUB, "GitHub"),
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

    ProjectStatePane #gantt-scroll {
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

    REFRESH_INTERVAL = 60

    def __init__(
        self,
        project_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._project_path = project_path or Path(".").resolve()
        self._refresh_timer: Timer | None = None
        self._provider = self._make_provider()

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
                with VerticalScroll(id="gantt-scroll"):
                    yield GanttTimeline(id="pane-gantt")

        # Canon state watcher (invisible, drives State view)
        yield CanonStateWidget(
            project_path=self._project_path,
            id="canon-state",
        )

        # --- State section (canon build + run) ---
        with TabbedContent(
            id=SECTION_BUILDER, classes="pane-section"
        ):
            with TabPane("State", id="tab-builder"):
                yield BuilderView(id="builder-view")

    def on_mount(self) -> None:
        # GitHub hidden by default, State visible
        self.query_one(f"#{SECTION_GITHUB}").display = False
        self.query_one(f"#{SECTION_BUILDER}").display = True
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
