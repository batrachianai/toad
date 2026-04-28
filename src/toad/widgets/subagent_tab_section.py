"""Subagents section for ``ProjectStatePane``.

This section appears on demand: it starts hidden and reveals itself when
the first subagent tab is opened. When the last tab closes it hides
again. Each tab hosts a ``Conversation`` + ``Agent`` pair produced by an
injectable ``agent_factory``, so tests and the socket layer can supply
stubs or real ACP subprocesses without this widget knowing the details.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import TabbedContent, TabPane

AgentFactory = Callable[[str, str], tuple[Widget, Any]]
"""Signature: ``factory(name, objective) -> (conversation_widget, agent)``."""


class SubagentTabSection(Vertical):
    """A ``ProjectStatePane`` section that hosts one tab per live subagent."""

    SECTION_ID = "section-subagents"

    DEFAULT_CSS = """
    SubagentTabSection {
        display: none;
        height: 1fr;
    }

    SubagentTabSection TabbedContent {
        height: 1fr;
    }
    """

    def __init__(
        self,
        project_path: Path,
        agent_factory: AgentFactory,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._project_path = project_path
        self._factory = agent_factory
        # Insertion-ordered: name -> agent
        self._agents: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield TabbedContent(id="subagents-tabs")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        return not self._agents

    @property
    def tab_names(self) -> list[str]:
        return list(self._agents.keys())

    def get_agent(self, name: str) -> Any | None:
        return self._agents.get(name)

    def open_tab(self, name: str, objective: str) -> str:
        """Open a new subagent tab. Returns the resolved unique name."""
        resolved = self._resolve_name(name)
        conversation, agent = self._factory(resolved, objective)
        self._agents[resolved] = agent
        tabs = self.query_one("#subagents-tabs", TabbedContent)
        pane = TabPane(resolved, conversation, id=self._tab_id(resolved))
        tabs.add_pane(pane)
        tabs.active = self._tab_id(resolved)
        self.display = True
        return resolved

    def close_tab(self, name: str) -> None:
        """Close a subagent tab. No-op if ``name`` is unknown.

        Fires the agent's ``done_event`` (if present) so any pending
        ``watch_subagent_completion`` coroutine injects a synthetic
        completion message into the Conductor's session.
        """
        if name not in self._agents:
            return
        agent = self._agents.pop(name)
        done_event = getattr(agent, "done_event", None)
        if done_event is not None:
            try:
                done_event.set()
            except Exception:
                pass
        tabs = self.query_one("#subagents-tabs", TabbedContent)
        tabs.remove_pane(self._tab_id(name))
        if not self._agents:
            self.display = False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_name(self, name: str) -> str:
        if name not in self._agents:
            return name
        i = 2
        while f"{name} {i}" in self._agents:
            i += 1
        return f"{name} {i}"

    @staticmethod
    def _tab_id(name: str) -> str:
        slug = name.lower().replace(" ", "-")
        return f"subagent-tab-{slug}"
