from contextlib import suppress
from dataclasses import dataclass
from itertools import zip_longest
import json
import os
from pathlib import Path
from random import shuffle
from typing import Literal, Self

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
from textual.reactive import reactive
from textual import containers
from textual import widgets

import toad
from toad.app import ToadApp
from toad.db import DB
from toad.pill import pill
from toad.widgets.directory_input import DirectoryInput
from toad.widgets.mandelbrot import Mandelbrot
from toad.widgets.condensed_path import CondensedPath
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
    session_id: str | None = None
    pk: int | None = None


@dataclass
class ChangeDirectory(Message):
    path: str


class DirectoryDisplay(containers.HorizontalGroup):

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    DEFAULT_CSS = """
    DirectoryDisplay {
        CondensedPath { display: block; }
        DirectoryInput { display: none; }
        &.-edit {
            CondensedPath { display: none}
            DirectoryInput { display: block; }
        }
    }
    """

    project_dir: reactive[Path] = reactive(Path)
    path = reactive("")
    edit = reactive(False, toggle_class="-edit")

    directory_input = getters.query_one(DirectoryInput)

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir
        self.path = str(project_dir)

    def watch_project_dir(self, path: Path) -> None:
        self.path = str(path)
        self.refresh(layout=True)

    def focus(self, scroll_visible=True) -> Self:
        self.edit = True
        self.directory_input.focus(scroll_visible=scroll_visible)
        return self

    @on(events.Click, "CondensedPath")
    def on_click(self) -> None:
        self.edit = True
        self.directory_input.focus()

    @on(events.DescendantBlur)
    def on_blur(self):
        self.action_dismiss()

    @on(widgets.Input.Submitted)
    def on_input_submitted(self, event: widgets.Input.Submitted) -> None:
        self.edit = False
        path = Path(event.value)
        if not path.is_dir():
            self.notify(
                f"Unable to change directory to {str(path)!r}",
                title="Change directory",
                severity="error",
            )
            return
        path = path.expanduser().resolve()
        self.post_message(ChangeDirectory(str(path)))

    def action_dismiss(self) -> None:
        self.edit = False
        self.directory_input.value = self.path

    def watch_edit(self, edit: bool) -> None:
        if not edit and self.directory_input.has_focus:
            self.directory_input.blur()

    def compose(self) -> ComposeResult:
        yield widgets.Label("📁 ")
        yield CondensedPath(self.path).data_bind(path=DirectoryDisplay.path)
        yield DirectoryInput(self.path, select_on_focus=False, compact=True).data_bind(
            value=DirectoryDisplay.path
        )


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


class LauncherGridSelect(GridSelect):

    HELP = """\
## Launcher

Your favorite agents.

- **1-9 a-f** Select agent
- **cursor keys** navigate agents
- **tab / shift+tab** Move to next / previous section
- **space** Launch highlighted agent
- **enter** Open agent details
"""
    BINDING_GROUP_TITLE = "Launcher"

    app = getters.app(ToadApp)
    BINDINGS = [
        Binding(
            "enter",
            "select",
            "Details",
            tooltip="Open agent details",
        ),
        Binding(
            "space",
            "launch",
            "Launch",
            tooltip="Launch highlighted agent",
        ),
    ]

    def action_details(self) -> None:
        if self.highlighted is None:
            return
        agent_item = self.children[self.highlighted]
        assert isinstance(agent_item, LauncherItem)
        self.post_message(StoreScreen.OpenAgentDetails(agent_item._agent["identity"]))

    def action_remove(self) -> None:
        agents = self.app.settings.get("launcher.agents", str).splitlines()
        if self.highlighted is None:
            return
        try:
            del agents[self.highlighted]
        except IndexError:
            pass
        else:
            self.app.settings.set("launcher.agents", "\n".join(agents))

    def action_launch(self) -> None:
        if self.highlighted is None:
            return
        child = self.children[self.highlighted]
        assert isinstance(child, LauncherItem)
        self.post_message(LaunchAgent(child.agent["identity"]))


class Launcher(containers.VerticalGroup):
    app = getters.app(ToadApp)
    grid_select = getters.query_one("#launcher-grid-select", LauncherGridSelect)
    DIGITS = "123456789ABCDEF"

    def __init__(
        self,
        agents: dict[str, Agent],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._agents = agents
        super().__init__(name=name, id=id, classes=classes)

    @property
    def highlighted(self) -> int | None:
        return self.grid_select.highlighted

    @highlighted.setter
    def highlighted(self, value: int) -> None:
        self.grid_select.highlighted = value

    def focus(self, scroll_visible: bool = True) -> Self:
        try:
            self.grid_select.focus(scroll_visible=scroll_visible)
        except NoMatches:
            pass
        return self

    def compose(self) -> ComposeResult:
        launcher_agents = list(
            dict.fromkeys(
                identity
                for identity in self.app.settings.get(
                    "launcher.agents", str
                ).splitlines()
                if identity.strip()
            )
        )
        agents = self._agents
        self.set_class(not launcher_agents, "-empty")
        if launcher_agents:
            with LauncherGridSelect(
                id="launcher-grid-select", min_column_width=32, max_column_width=32
            ):
                for digit, identity in zip_longest(self.DIGITS, launcher_agents):
                    if identity is None:
                        break
                    if identity in agents:
                        yield LauncherItem(digit or "", agents[identity])

        if not launcher_agents:
            yield widgets.Label("Choose your fighter below!", classes="no-agents")

    def launch_highlighted(self) -> None:
        self.grid_select.action_launch()


class LauncherItem(containers.VerticalGroup):
    """An entry in the Agent grid select."""

    def __init__(self, digit: str, agent: Agent) -> None:
        self._digit = digit
        self._agent = agent
        super().__init__()

    @property
    def agent(self) -> Agent:
        return self._agent

    def compose(self) -> ComposeResult:
        agent = self._agent
        with containers.HorizontalGroup():
            if self._digit:
                yield widgets.Digits(self._digit)
            with containers.VerticalGroup():
                yield widgets.Label(agent["name"], id="name")
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
        Binding(
            "null",
            "quick_launch",
            "Quick launch",
            key_display="1-9 a-f",
        ),
        Binding("ctrl+r", "resume", "Resume", tooltip="Resume a previous session"),
        Binding(
            "ctrl+d",
            "directory",
            "Directory",
            tooltip="Change project directory",
        ),
    ]

    agents_view = getters.query_one("#agents-view", AgentGridSelect)
    launcher = getters.query_one("#launcher", Launcher)
    container = getters.query_one("#container", Container)

    project_dir: reactive[Path] = reactive(Path)

    app = getters.app(ToadApp)

    @dataclass
    class OpenAgentDetails(Message):
        identity: str

    def __init__(
        self, name: str | None = None, id: str | None = None, classes: str | None = None
    ):
        self._agents: dict[str, Agent] = {}
        super().__init__(name=name, id=id, classes=classes)
        self.project_dir = self.app.project_dir

    @property
    def agents(self) -> dict[str, Agent]:
        return self._agents

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="title-container"):
            with containers.Grid(id="title-grid"):
                yield Mandelbrot()
                yield widgets.Label(self.get_info(), id="info")
        yield DirectoryDisplay(self.project_dir).data_bind(
            project_dir=StoreScreen.project_dir
        )
        yield Container(id="container", can_focus=False)
        yield widgets.Footer()

    def get_info(self) -> Content:
        toad_version = toad.get_version()
        content = Content.assemble(
            Content.from_markup("🐸 Toad"),
            pill(f"v{toad_version}", "$primary-muted", "$text-primary"),
            ("\nThe universal interface for AI in your terminal", "$text-success"),
            (
                "\nSoftware lovingly crafted by hand (with a dash of AI) in Edinburgh, Scotland",
                "dim",
            ),
            "\n",
            (
                Content.from_markup(
                    "\nConsider sponsoring [@click=screen.url('https://github.com/sponsors/willmcgugan')]@willmcgugan[/] to support future updates"
                )
            ),
            "\n\n",
            (
                Content.from_markup(
                    "[dim]Code: [@click=screen.url('https://github.com/batrachianai/toad')]Repository[/] "
                    "Bugs: [@click=screen.url('https://github.com/batrachianai/toad/discussions')]Discussions[/]"
                )
            ),
        )

        return content

    def action_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def compose_agents(self) -> ComposeResult:
        agents = self._agents

        yield Launcher(agents, id="launcher")

        ordered_agents = sorted(
            agents.values(), key=lambda agent: agent["name"].casefold()
        )

        recommended_agents = [
            agent for agent in ordered_agents if agent.get("recommended", False)
        ]
        # Shuffle reccomended agents so none has priority
        shuffle(recommended_agents)
        if recommended_agents:
            with containers.VerticalGroup(id="sponsored-agents", classes="recommended"):
                yield widgets.Static("Recommended", classes="heading")
                with AgentGridSelect(classes="agents-picker", min_column_width=40):
                    for agent in recommended_agents:
                        yield AgentItem(agent)

        coding_agents = [agent for agent in ordered_agents if agent["type"] == "coding"]
        if coding_agents:
            yield widgets.Static("Coding agents", classes="heading")
            with AgentGridSelect(classes="agents-picker", min_column_width=40):
                for agent in coding_agents:
                    yield AgentItem(agent)

        chat_bots = [agent for agent in ordered_agents if agent["type"] == "chat"]
        if chat_bots:
            yield widgets.Static("Chat & more", classes="heading")
            with AgentGridSelect(classes="agents-picker", min_column_width=40):
                for agent in chat_bots:
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

    @on(GridSelect.Selected, "#launcher GridSelect")
    @work
    async def on_launcher_selected(self, event: GridSelect.Selected):
        launcher_item = event.selected_widget
        assert isinstance(launcher_item, LauncherItem)

        from toad.screens.agent_modal import AgentModal

        modal_response = await self.app.push_screen_wait(
            AgentModal(launcher_item.agent)
        )
        self.app.save_settings()
        if modal_response == "launch":
            self.post_message(LaunchAgent(launcher_item.agent["identity"]))

    @on(ChangeDirectory)
    def on_change_directory(self, event: ChangeDirectory) -> None:
        self.project_dir = Path(event.path)
        print(self.project_dir)

    @work
    async def launch_agent(
        self,
        agent_identity: str,
        agent_session_id: str | None,
        session_pk: int | None = None,
    ) -> None:
        from toad.screens.main import MainScreen

        agent: Agent | None = None
        if session_pk is not None:
            db = DB()
            session = await db.session_get(session_pk)
            if session is not None:
                meta = json.loads(session["meta_json"])
                if agent_data := meta.get("agent_data"):
                    agent = agent_data

        if agent is None:
            try:
                agent = self.agents[agent_identity]
            except KeyError:
                self.notify("Agent not found", title="Launch agent", severity="error")
                return
        project_path = Path(self.app.project_dir or os.getcwd())

        def get_screen():
            screen = MainScreen(
                project_path, agent, agent_session_id, session_pk=session_pk
            ).data_bind(
                column=ToadApp.column,
                column_width=ToadApp.column_width,
            )
            return screen

        await self.app.new_session_screen(get_screen)

    @on(LaunchAgent)
    def on_launch_agent(self, message: LaunchAgent) -> None:
        self.launch_agent(message.identity, message.session_id, message.pk)

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
        key, value = setting
        if key == "launcher.agents":
            await self.launcher.recompose()

            def focus_screen():
                try:
                    self.screen.query(GridSelect).focus()
                except Exception:
                    pass

            self.call_later(focus_screen)

    def on_key(self, event: events.Key) -> None:
        if event.character is None:
            return
        LAUNCHER_KEYS = "123456789abcdef"
        if event.character in LAUNCHER_KEYS:
            launch_item_offset = LAUNCHER_KEYS.find(event.character)
            try:
                self.launcher.grid_select.children[launch_item_offset]
            except IndexError:
                self.notify(
                    f"No agent on key [b]{LAUNCHER_KEYS[launch_item_offset]}",
                    title="Quick launch",
                    severity="error",
                )
                self.app.bell()
                return
            self.launcher.focus()
            self.launcher.highlighted = launch_item_offset
            self.launcher.launch_highlighted()

    def action_quick_launch(self) -> None:
        self.launcher.focus()

    @work
    async def action_resume(self) -> None:
        from toad.screens.session_resume_modal import SessionResumeModal

        session = await self.app.push_screen_wait(SessionResumeModal())
        if session is not None:
            self.post_message(
                LaunchAgent(
                    session["agent_identity"],
                    session["agent_session_id"],
                    pk=session["id"],
                )
            )

    async def action_directory(self) -> None:
        if (directory_display := self.query_one_optional(DirectoryDisplay)) is not None:
            directory_display.focus()


if __name__ == "__main__":
    from toad.app import ToadApp

    app = ToadApp(mode="store")

    app.run()
