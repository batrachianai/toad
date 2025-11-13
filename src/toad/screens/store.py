from importlib.metadata import version
from itertools import zip_longest
from pathlib import Path
from typing import Self

from textual.binding import Binding
from textual.screen import Screen
from textual import events
from textual import work
from textual import getters
from textual import on
from textual.app import ComposeResult
from textual.content import Content
from textual.css.query import NoMatches
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
            yield widgets.Label(
                pill(agent["type"], "$primary-muted", "$text-primary"), id="type"
            )
        yield widgets.Label(agent["author_name"], id="author")
        yield widgets.Static(agent["description"], id="description")


class LauncherGridSelect(GridSelect):
    BINDINGS = [
        Binding("enter", "select", "Launch"),
    ]


class Launcher(containers.VerticalGroup):
    app = getters.app(ToadApp)
    grid_select = getters.query_one("#launcher-grid-select", GridSelect)
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
        launcher_set = frozenset(
            self.app.settings.get("launcher.agents", str).splitlines()
        )
        agents = self._agents

        if launcher_set:
            with LauncherGridSelect(
                id="launcher-grid-select", min_column_width=40, max_column_width=40
            ):
                for digit, identity in zip_longest(self.DIGITS, launcher_set):
                    if identity is None:
                        break
                    yield LauncherItem(digit or "", agents[identity])
        else:
            yield widgets.Label("Chose your fighter below!", classes="instruction-text")


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


class StoreScreen(Screen):
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
    ]

    agents_view = getters.query_one("#agents-view", GridSelect)
    launcher = getters.query_one("#launcher", Launcher)

    app = getters.app(ToadApp)

    def __init__(
        self, name: str | None = None, id: str | None = None, classes: str | None = None
    ):
        self._agents: dict[str, Agent] = {}
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        with containers.VerticalScroll(id="container"):
            with containers.VerticalGroup(id="title-container"):
                with containers.Grid(id="title-grid"):
                    yield Mandelbrot()
                    yield widgets.Label(self.get_info(), id="info")
            # yield widgets.LoadingIndicator()
        yield widgets.Footer()

    def get_info(self) -> Content:
        content = Content.assemble(
            Content.from_markup("Toad"),
            pill(f"v{version('toad')}", "$primary-muted", "$text-primary"),
            ("\nThe universal interface for AI in your terminal", "$text-success"),
            (
                "\nSoftware lovingly crafted by hand (with a dash of AI) in Edinburgh, Scotland",
                "dim",
            ),
            "\n",
            (
                Content.from_markup(
                    "\nConsider sponsoring [@click=screen.url('https://github.com/sponsors/willmcgugan')]@willmcgugan[/] to support development of Toad!"
                )
            ),
            "\n\n",
            (
                Content.from_markup(
                    "[dim]Code: [@click=screen.url('https://github.com/Textualize/toad')]Repository[/] "
                    "Bugs: [@click=screen.url('https://github.com/Textualize/toad/discussions')]Discussions[/]"
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
        yield widgets.Static("Agents", classes="heading")
        with GridSelect(id="agents-view", min_column_width=40):
            for agent in ordered_agents:
                yield AgentItem(agent)

    @on(GridSelect.Selected, "#agents-view")
    @work
    async def on_grid_select_selected(self, event: GridSelect.Selected):
        assert isinstance(event.selected_widget, AgentItem)
        from toad.screens.agent_modal import AgentModal

        await self.app.push_screen_wait(AgentModal(event.selected_widget.agent))
        self.app.save_settings()

    @on(GridSelect.Selected, "#launcher GridSelect")
    @work
    async def on_launcher_selected(self, event: GridSelect.Selected):
        launcher_item = event.selected_widget
        assert isinstance(launcher_item, LauncherItem)

        agent = launcher_item.agent
        from toad.screens.main import MainScreen

        project_path = Path(self.app.project_dir or "./")

        screen = MainScreen(project_path, agent)
        await self.app.push_screen_wait(screen)

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
            # await self.query(widgets.LoadingIndicator).remove()
            await self.query_one("#container").mount_compose(self.compose_agents())

    def setting_updated(self, setting: tuple[str, object]) -> None:
        key, value = setting
        if key == "launcher.agents":
            self.launcher.refresh(recompose=True)

    def on_key(self, event: events.Key) -> None:
        if event.character is None:
            return
        if event.character in "123456789abcdef":
            launch_item_offset = "123456789abcdef".find(event.character)
            self.launcher.focus()
            try:
                launch_item = self.launcher.grid_select.children[launch_item_offset]
            except IndexError:
                self.notify(
                    f"No agent on key [b]{launch_item_offset}",
                    title="Quick launch",
                    severity="error",
                )
                return
            self.launcher.highlighted = launch_item_offset

    def action_quick_launch(self) -> None:
        self.launcher.focus()


if __name__ == "__main__":
    from toad.app import ToadApp

    app = ToadApp(mode="store")

    app.run()
