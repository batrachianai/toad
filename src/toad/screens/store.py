from contextlib import suppress
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal

from textual.binding import Binding
from textual.screen import Screen
from textual import events
from textual import work
from textual import getters
from textual import on
from textual.app import ComposeResult
from textual.content import Content
from textual.css.query import NoMatches
from textual.message import Message
from textual import containers
from textual import widgets

import toad
from toad.app import ToadApp
from toad.pill import pill
from toad.widgets.mandelbrot import Mandelbrot
from toad.widgets.grid_select import GridSelect
from toad.agent_schema import Agent
from toad.agents import read_agents


QR = """\
█▀▀▀▀▀█ ▄█ ▄▄█▄▄█ █▀▀▀▀▀█
█ ███ █ ▄█▀█▄▄█▄  █ ███ █
█ ▀▀▀ █ ▄ █ ▀▀▄▄▀ █ ▀▀▀ █
▀▀▀▀▀▀▀ ▀ ▀ ▀ █ █ ▀▀▀▀▀▀▀
█▀██▀ ▀█▀█▀▄▄█   ▀ █ ▀ █ 
 █ ▀▄▄▀▄▄█▄▄█▀██▄▄▄▄ ▀ ▀█
▄▀▄▀▀▄▀ █▀▄▄▄▀▄ ▄▀▀█▀▄▀█▀
█ ▄ ▀▀▀█▀ █ ▀ █▀ ▀ ██▀ ▀█
▀  ▀▀ ▀▀▄▀▄▄▀▀▄▀█▀▀▀█▄▀  
█▀▀▀▀▀█ ▀▄█▄▀▀  █ ▀ █▄▀▀█
█ ███ █ ██▄▄▀▀█▀▀██▀█▄██▄
█ ▀▀▀ █ ██▄▄ ▀  ▄▀ ▄▄█▀ █
▀▀▀▀▀▀▀ ▀▀▀  ▀   ▀▀▀▀▀▀▀▀"""


@dataclass
class LaunchAgent(Message):
    identity: str


class AgentItem(containers.VerticalGroup):
    """An entry in the Agent grid select."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        super().__init__()

    @property
    def agent(self) -> Agent:
        return self._agent

    def compose(self) -> ComposeResult:
        agent = self._agent
        with containers.Grid():
            yield widgets.Label(agent["name"], id="name")
            tag = pill(agent["type"], "$primary-muted 50%", "$text-primary")
            yield widgets.Label(tag, id="type")
        yield widgets.Label(agent["author_name"], id="author")
        yield widgets.Static(agent["description"], id="description")


class AgentGridSelect(GridSelect):
    HELP = """\
## Agent select

- **cursor keys** Navigate agents
- **tab / shift+tab** Move to next / previous section
- **enter** Open agent details
- **space** Launch the agent (if installed)
"""
    BINDINGS = [
        Binding("enter", "select", "Details", tooltip="Open agent details"),
        Binding("space", "launch", "Launch", tooltip="Launch highlighted agent"),
    ]
    BINDING_GROUP_TITLE = "Agent Select"

    def action_launch(self) -> None:
        if self.highlighted is None:
            return
        child = self.children[self.highlighted]
        assert isinstance(child, AgentItem)
        self.post_message(LaunchAgent(child.agent["identity"]))


class Container(containers.VerticalScroll):
    BINDING_GROUP_TITLE = "View"

    def allow_focus(self) -> bool:
        """Only allow focus when we can scroll."""
        return super().allow_focus() and self.show_vertical_scrollbar


class StoreScreen(Screen):
    BINDING_GROUP_TITLE = "Screen"
    CSS_PATH = "store.tcss"
    FOCUS_GROUP = Binding.Group("Focus")
    BINDINGS = [
        Binding(
            "tab",
            "app.focus_next",
            "Focus Next",
            group=FOCUS_GROUP,
        ),
        Binding(
            "shift+tab",
            "app.focus_previous",
            "Focus Previous",
            group=FOCUS_GROUP,
        ),
    ]

    container = getters.query_one("#container", Container)

    app = getters.app(ToadApp)

    @dataclass
    class OpenAgentDetails(Message):
        identity: str

    def __init__(
        self, name: str | None = None, id: str | None = None, classes: str | None = None
    ):
        self._agents: dict[str, Agent] = {}
        super().__init__(name=name, id=id, classes=classes)

    @property
    def agents(self) -> dict[str, Agent]:
        return self._agents

    def compose(self) -> ComposeResult:
        yield Container(id="container", can_focus=False)
        yield widgets.Footer()

    def action_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def compose_agents(self) -> ComposeResult:
        agents = self._agents

        # Simple display - just show all agents without categories
        ordered_agents = sorted(
            agents.values(), key=lambda agent: agent["name"].casefold()
        )

        if ordered_agents:
            yield widgets.Static("Select an agent", classes="heading")
            with AgentGridSelect(classes="agents-picker", min_column_width=40):
                for agent in ordered_agents:
                    yield AgentItem(agent)

    def move_focus(self, direction: Literal[-1] | Literal[+1]) -> None:
        if isinstance(self.focused, GridSelect):
            focus_chain = list(self.query(GridSelect))
            if self.focused in focus_chain:
                index = focus_chain.index(self.focused)
                new_focus = focus_chain[(index + direction) % len(focus_chain)]
                if direction == -1:
                    new_focus.highlight_last()
                else:
                    new_focus.highlight_first()
                new_focus.focus(scroll_visible=False)

    @on(GridSelect.LeaveUp)
    def on_grid_select_leave_up(self, event: GridSelect.LeaveUp):
        event.stop()
        self.move_focus(-1)

    @on(GridSelect.LeaveDown)
    def on_grid_select_leave_down(self, event: GridSelect.LeaveUp):
        event.stop()
        self.move_focus(+1)

    @on(GridSelect.Selected, ".agents-picker")
    @work
    async def on_grid_select_selected(self, event: GridSelect.Selected):
        assert isinstance(event.selected_widget, AgentItem)
        from toad.screens.agent_modal import AgentModal

        modal_response = await self.app.push_screen_wait(
            AgentModal(event.selected_widget.agent)
        )
        self.app.save_settings()
        if modal_response == "launch":
            self.post_message(LaunchAgent(event.selected_widget.agent["identity"]))

    @on(OpenAgentDetails)
    @work
    async def open_agent_detail(self, message: OpenAgentDetails) -> None:
        from toad.screens.agent_modal import AgentModal

        try:
            agent = self._agents[message.identity]
        except KeyError:
            return
        modal_response = await self.app.push_screen_wait(AgentModal(agent))
        self.app.save_settings()
        if modal_response == "launch":
            self.post_message(LaunchAgent(agent["identity"]))

    @work
    async def launch_agent(self, agent_identity: str) -> None:
        from toad.screens.main import MainScreen

        agent = self.agents[agent_identity]
        project_path = Path(self.app.project_dir or os.getcwd())
        screen = MainScreen(project_path, agent).data_bind(
            column=ToadApp.column,
            column_width=ToadApp.column_width,
        )
        await self.app.push_screen_wait(screen)

    @on(LaunchAgent)
    def on_launch_agent(self, message: LaunchAgent) -> None:
        self.launch_agent(message.identity)

    @work
    async def on_mount(self) -> None:
        self.app.settings_changed_signal.subscribe(self, self.setting_updated)
        try:
            self._agents = await read_agents()
        except Exception as error:
            self.notify(
                f"Failed to read agents data ({error})",
                title="Agents data",
                severity="error",
            )
        else:
            await self.container.mount_compose(self.compose_agents())
            with suppress(NoMatches):
                first_grid = self.container.query(GridSelect).first()
                first_grid.focus(scroll_visible=False)

    async def setting_updated(self, setting: tuple[str, object]) -> None:
        # No launcher settings to update anymore
        pass


if __name__ == "__main__":
    from toad.app import ToadApp

    app = ToadApp(mode="store")

    app.run()
