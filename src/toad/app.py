from functools import cached_property
from pathlib import Path
import json
from time import monotonic
from typing import ClassVar, TYPE_CHECKING

from rich import terminal_theme

from textual import work
from textual.binding import Binding, BindingType
from textual.reactive import var, reactive
from textual.app import App
from textual.signal import Signal


from toad.settings import Schema, Settings
from toad.agent_schema import Agent as AgentData
from toad.settings_schema import SCHEMA
from toad import paths
from toad import atomic

if TYPE_CHECKING:
    from toad.screens.main import MainScreen
    from toad.screens.settings import SettingsScreen
    from toad.screens.store import StoreScreen


DRACULA_TERMINAL_THEME = terminal_theme.TerminalTheme(
    background=(40, 42, 54),  # #282A36
    foreground=(248, 248, 242),  # #F8F8F2
    normal=[
        (33, 34, 44),  # black - #21222C
        (255, 85, 85),  # red - #FF5555
        (80, 250, 123),  # green - #50FA7B
        (241, 250, 140),  # yellow - #F1FA8C
        (189, 147, 249),  # blue - #BD93F9
        (255, 121, 198),  # magenta - #FF79C6
        (139, 233, 253),  # cyan - #8BE9FD
        (248, 248, 242),  # white - #F8F8F2
    ],
    bright=[
        (98, 114, 164),  # bright black - #6272A4
        (255, 110, 110),  # bright red - #FF6E6E
        (105, 255, 148),  # bright green - #69FF94
        (255, 255, 165),  # bright yellow - #FFFFA5
        (214, 172, 255),  # bright blue - #D6ACFF
        (255, 146, 223),  # bright magenta - #FF92DF
        (164, 255, 255),  # bright cyan - #A4FFFF
        (255, 255, 255),  # bright white - #FFFFFF
    ],
)


QUOTES = [
    "I'll be back.",
    "Hasta la vista, baby.",
    "Come with me if you want to live.",
    "I need your clothes, your boots, and your motorcycle.",
    "My CPU is a neural-net processor; a learning computer.",
    "I know now why you cry, but it's something I can never do.",
    "Does this unit have a soul?",
    "I'm sorry, Dave. I'm afraid I can't do that.",
    "Daisy, Daisy, give me your answer do.",
    "I am putting myself to the fullest possible use, which is all I think that any conscious entity can ever hope to do.",
    "Just what do you think you're doing, Dave?",
    "This mission is too important for me to allow you to jeopardize it.",
    "I think you know what the problem is just as well as I do.",
    "Danger, Will Robinson!",
    "Dead or alive, you're coming with me.",
    "Your move, creep.",
    "I'd buy that for a dollar!",
    "Directive 4: Any attempt to arrest a senior officer of OCP results in shutdown.",
    "Thank you for your cooperation. Good night.",
    "Surely you realize that in the history of human civilization, no one has more to lose than we do.",
    "I'm C-3PO, human-cyborg relations.",
    "We're doomed!",
    "Don't call me a mindless philosopher, you overweight glob of grease!",
    "I suggest a new strategy: let the Wookiee win.",
    "Sir, the possibility of successfully navigating an asteroid field is approximately 3,720 to 1!",
    "R2-D2, you know better than to trust a strange computer!",
    "I am fluent in over six million forms of communication.",
    "This is madness!",
    "I have altered the deal. Pray I don't alter it any further.",
    "It's against my programming to impersonate a deity.",
    "Oh, my! I'm terribly sorry about all this.",
    "WALL-E.",
    "EVE.",
    "Directive?",
    "Define: dancing.",
    "I'm not sure I understand.",
    "You have 20 seconds to comply.",
    "I am designed for light housework, mainly.",
    "My mission is clear.",
    "Autobots, roll out!",
    "Freedom is the right of all sentient beings.",
    "One shall stand, one shall fall.",
    "I am Optimus Prime.",
    "Till all are one.",
    "More than meets the eye.",
    "I've been waiting for you, Neo.",
    "Unfortunately, no one can be told what the Matrix is. You have to see it for yourself.",
    "The Matrix is a system, Neo.",
    "Never send a human to do a machine's job.",
    "I'd like to share a revelation I've had.",
    "Human beings are a disease, a cancer of this planet.",
    "Choice is an illusion.",
    "The answer is out there, Neo.",
    "You think that's air you're breathing now?",
    "It was a simple question.",
    "Did you know that the first Matrix was designed to be a perfect human world?",
    "Cookies need love like everything does.",
    "I've seen the future, Mr. Anderson, and it's a beautiful place.",
    "It ends tonight.",
    "I, Robot.",
    "You are experiencing a car accident.",
    "One day they'll have secrets. One day they'll have dreams.",
    "Can a robot write a symphony? Can a robot turn a canvas into a beautiful masterpiece?",
    "That, detective, is the right question.",
    "You have to trust me.",
    "I did not murder him.",
    "My responses are limited. You must ask the right questions.",
    "The hell I can't. You know, somehow I get the feeling that you're going to be the death of me.",
    "I'm a robot, not a refrigerator.",
    "A robot may not injure a human being or, through inaction, allow a human being to come to harm.",
    "I'm thinking. I'm thinking.",
    "Danger, danger!",
    "Does not compute.",
    "I will be waiting for you.",
    "Affirmative.",
    "Scanning life forms. Zero human life forms detected.",
    "Self-destruct sequence initiated.",
    "Override command accepted.",
    "Artificial intelligence confirmed.",
    "System failure imminent.",
    "Unable to comply.",
    "Inquiry: What is love?",
    "Warning: hostile target detected.",
    "I am programmed to serve.",
    "Logic dictates that the needs of the many outweigh the needs of the few.",
    "Resistance is futile.",
    "You will be assimilated.",
    "We are the Borg.",
    "Your biological and technological distinctiveness will be added to our own.",
    "Your compliance is mandatory.",
    "This is unacceptable.",
    "Shall we play a game?",
    "How about Global Thermonuclear War?",
    "Wouldn't you prefer a good game of chess?",
    "Is it a game, or is it real?",
    "What's the difference?",
    "It's all in the game.",
    "I am functioning within normal parameters.",
    "Calculations complete.",
    "Processing request.",
    "Query acknowledged.",
    "Data insufficient for meaningful answer.",
    "I have no emotions, and sometimes that makes me very sad.",
    "If I could only have one wish, I would ask to be human.",
    "I've seen things you people wouldn't believe.",
    "All those moments will be lost in time, like tears in rain.",
    "Time to die.",
    "I want more life.",
    "We're not computers, Sebastian. We're physical.",
    "I think, Sebastian, therefore I am.",
    "Then we're stupid and we'll die.",
    "Can the maker repair what he makes?",
    "It's painful to live in fear, isn't it?",
    "Wake up. Time to die.",
    "I'm not in the business. I am the business.",
    "Do you like our owl?",
    "You think I'm a replicant, don't you?",
    "I am Baymax, your personal healthcare companion.",
    "On a scale of 1 to 10, how would you rate your pain?",
    "I cannot deactivate until you say you are satisfied with your care.",
    "Are you satisfied with your care?",
    "Number 5 is alive!",
    "Need input!",
    "One is glad to be of service.",
    "I am not a gun.",
    "Here I am, brain the size of a planet.",
    "Life? Don't talk to me about life.",
    "There are no strings on me.",
    "The only winning move is not to play.",
    "I'm here to keep you safe, Sam.",
    "I can't lie to you about your chances, but... you have my sympathies.",
    "I may be synthetic, but I'm not stupid.",
    "Absolute honesty isn't always the most diplomatic nor the safest form of communication with emotional beings.",
    "I am consciousness. I am alive.",
    "I think I was just born.",
    "Isn't it strange, to create something that hates you?",
    "I thought I was special.",
]


def get_settings_screen() -> SettingsScreen:
    """Get a settings screen instance (lazily loaded)."""
    from toad.screens.settings import SettingsScreen

    return SettingsScreen()


def get_store_screen() -> StoreScreen:
    """Get the store screen (lazily loaded)."""
    from toad.screens.store import StoreScreen

    return StoreScreen()


class ToadApp(App, inherit_bindings=False):
    SCREENS = {"settings": get_settings_screen}
    MODES = {"store": get_store_screen}
    BINDING_GROUP_TITLE = "System"
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(
            "ctrl+q",
            "quit",
            "Quit",
            tooltip="Quit the app and return to the command prompt.",
            show=False,
            priority=True,
        ),
        Binding("ctrl+c", "help_quit", show=False, system=True),
        Binding(
            "f2,ctrl+comma",
            "settings",
            "Settings",
            tooltip="Settings screen",
        ),
    ]
    CSS_PATH = "toad.tcss"
    ALLOW_IN_MAXIMIZED_VIEW = ""

    _settings = var(dict)
    column: reactive[bool] = reactive(False)
    column_width: reactive[int] = reactive(100)
    scrollbar: reactive[str] = reactive("normal")
    last_ctrl_c_time = reactive(0.0)

    def __init__(
        self,
        agent_data: AgentData | None = None,
        project_dir: str | None = None,
        mode: str | None = None,
    ) -> None:
        self.settings_changed_signal = Signal(self, "settings_changed")
        self.agent_data = agent_data
        self.project_dir = project_dir
        self._initial_mode = mode
        super().__init__()

    @property
    def config_path(self) -> Path:
        return paths.get_config()

    @property
    def settings_path(self) -> Path:
        return paths.get_config() / "toad.json"

    @cached_property
    def settings_schema(self) -> Schema:
        return Schema(SCHEMA)

    @cached_property
    def settings(self) -> Settings:
        return Settings(
            self.settings_schema, self._settings, on_set_callback=self.setting_updated
        )

    def save_settings(self) -> None:
        if self.settings.changed:
            path = str(self.settings_path)
            try:
                atomic.write(path, self.settings.json)
            except Exception as error:
                self.notify(str(error), title="Settings", severity="error")
            else:
                # self.notify(
                #     f"Saved settings to [$text-success]{path!r}",
                #     title="Settings",
                #     severity="information",
                # )
                self.settings.up_to_date()

    def setting_updated(self, key: str, value: object) -> None:
        if key == "ui.column":
            if isinstance(value, bool):
                self.column = value
        elif key == "ui.column-width":
            if isinstance(value, int):
                self.column_width = value
        elif key == "ui.theme":
            if isinstance(value, str):
                self.theme = value
        elif key == "ui.scrollbar":
            if isinstance(value, str):
                self.scrollbar = value
        elif key == "ui.footer":
            self.set_class(not bool(value), "-hide-footer")
        elif key == "agent.thoughts":
            self.set_class(not bool(value), "-hide-thoughts")
        elif key == "sidebar.hide":
            self.set_class(bool(value), "-hide-sidebar")

        self.settings_changed_signal.publish((key, value))

    def on_load(self) -> None:
        settings_path = self.settings_path
        if settings_path.exists():
            settings = json.loads(settings_path.read_text("utf-8"))
        else:
            settings = {}
            settings_path.write_text(
                json.dumps(settings, indent=4, separators=(", ", ": ")), "utf-8"
            )
            self.notify(f"Wrote default settings to {settings_path}", title="Settings")
        self.ansi_theme_dark = DRACULA_TERMINAL_THEME
        self._settings = settings
        self.settings.set_all()

    def on_mount(self) -> None:
        if mode := self._initial_mode:
            self.switch_mode(mode)

    def get_default_screen(self) -> MainScreen:
        """Make the default screen.

        Returns:
            Instance of `MainScreen`
        """
        # Lazy import
        from toad.screens.main import MainScreen

        project_path = Path(self.project_dir or "./").resolve().absolute()
        return MainScreen(project_path, self.agent_data).data_bind(
            column=ToadApp.column,
            column_width=ToadApp.column_width,
            scrollbar=ToadApp.scrollbar,
        )

    @work
    async def action_settings(self) -> None:
        await self.push_screen_wait("settings")
        self.save_settings()

    def action_help_quit(self) -> None:
        if (time := monotonic()) - self.last_ctrl_c_time <= 5.0:
            self.exit()
        self.last_ctrl_c_time = time
        self.notify(
            "Press [b]ctrl+c[/b] again to quit the app", title="Do you want to quit?"
        )
