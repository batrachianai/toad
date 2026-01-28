from importlib.resources import files
from datetime import datetime, timezone
from functools import cached_property
import os
from pathlib import Path
import platform
import json
from time import monotonic
from typing import Any, ClassVar, TYPE_CHECKING

from rich import terminal_theme

from textual import on, work
from textual.binding import Binding, BindingType
from textual.content import Content
from textual.reactive import var, reactive
from textual.app import App
from textual import events
from textual.signal import Signal
from textual.timer import Timer
from textual.notifications import Notify

import toad
from toad.db import DB
from toad.settings import Schema, Settings
from toad.agent_schema import Agent as AgentData
from toad.settings_schema import SCHEMA
from toad.version import VersionMeta
from toad import paths
from toad import atomic

if TYPE_CHECKING:
    from toad.screens.main import MainScreen
    from toad.screens.settings import SettingsScreen
    from toad.screens.store import StoreScreen
    from toad.db import DB


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
    """The top level app."""

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
        Binding("f1", "toggle_help_panel", "Help", priority=True),
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
    update_required: reactive[bool] = reactive(False)
    terminal_title: var[str] = var("Toad")
    terminal_title_icon: var[str] = var("🐸")
    terminal_title_flash = var(0)
    terminal_title_blink = var(False)

    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (100, "-wide")]

    def __init__(
        self,
        agent_data: AgentData | None = None,
        project_dir: str | None = None,
        mode: str | None = None,
    ) -> None:
        """Toad app.

        Args:
            agent_data: Agent data to run.
            project_dir: Project directory.
            mode: Initial mode.
            agent: Agent identity or shor name.
        """
        self.settings_changed_signal = Signal(self, "settings_changed")
        self.agent_data = agent_data
        self.project_dir = (
            None if project_dir is None else Path(project_dir).expanduser().resolve()
        )
        self._initial_mode = mode
        self.version_meta: VersionMeta | None = None
        self._supports_pyperclip: bool | None = None
        self._terminal_title_flash_timer: Timer | None = None

        super().__init__()

    @property
    def config_path(self) -> Path:
        return paths.get_config()

    @property
    def settings_path(self) -> Path:
        return paths.get_config() / "toad.json"

    @property
    def db_path(self) -> Path:
        return paths.get_state() / "toad.db"

    async def get_db(self) -> DB:
        """Get an instance of the database."""
        db = DB()
        return db

    @cached_property
    def settings_schema(self) -> Schema:
        return Schema(SCHEMA)

    @cached_property
    def version(self) -> str:
        """Version of the app."""
        from toad import get_version

        return get_version()

    @cached_property
    def settings(self) -> Settings:
        """App settings"""
        return Settings(
            self.settings_schema, self._settings, on_set_callback=self.setting_updated
        )

    @cached_property
    def anon_id(self) -> str:
        """An anonymous ID for usage collection."""
        if not (anon_id := self.settings.get("anon_id", str, expand=False)):
            # Create a random UUID on demand
            import uuid

            anon_id = str(uuid.uuid4())
            self.settings.set("anon_id", anon_id)
            self.save_settings()
            self.call_later(self.capture_event, "toad-install")
        return anon_id

    def copy_to_clipboard(self, text: str) -> None:
        """Override copy to clipboard to use pyperclip first, then OSC 52.

        Args:
            text: Text to copy.
        """
        if self._supports_pyperclip is None:
            try:
                import pyperclip
            except ImportError:
                self._supports_pyperclip = False
            else:
                self._supports_pyperclip = True

        if self._supports_pyperclip:
            import pyperclip

            try:
                pyperclip.copy(text)
            except Exception:
                pass
        super().copy_to_clipboard(text)

    def update_terminal_title(self) -> None:
        """Update the terminal title."""
        screen_title = self.screen.title

        title = (
            f"{self.terminal_title} — {screen_title}"
            if screen_title
            else self.terminal_title
        )
        icon = self.terminal_title_icon
        blink = self.terminal_title_blink

        if self.terminal_title_flash:
            if blink:
                terminal_title = f"{icon} {title}"
            else:
                terminal_title = f"👉 {title}" if title else icon
        else:
            terminal_title = f"{icon} {title}"

        if driver := self._driver:
            driver.write(f"\033]0;{terminal_title}\007")

    def watch_terminal_title_blink(self) -> None:
        self.update_terminal_title()

    def watch_terminal_title_flash(self, terminal_title_flash: int) -> None:

        if not self.settings.get("notifications.blink_title", bool):
            # Ignore if blink title is disabled
            return

        def toggle_blink() -> None:
            self.terminal_title_blink = not self.terminal_title_blink

        if terminal_title_flash:
            if self._terminal_title_flash_timer is None:
                self._terminal_title_flash_timer = self.set_interval(0.5, toggle_blink)
        else:
            if self._terminal_title_flash_timer is not None:
                self._terminal_title_flash_timer.stop()
                self.terminal_title_blink = False
                self._terminal_title_flash_timer = None
        self.update_terminal_title()

    def watch_terminal_title(self, title: str) -> None:
        self.update_terminal_title()

    def terminal_alert(self, flash: bool = True) -> None:
        if flash:
            self.terminal_title_flash += 1
        else:
            self.terminal_title_flash -= 1

    @cached_property
    def term_program(self) -> str:
        """An identifier for the terminal software."""
        if term_program := os.environ.get("TERM_PROGRAM"):
            return term_program

        # Windows Terminal
        if "WT_SESSION" in os.environ:
            return "Windows Terminal"

        # Kitty
        if "KITTY_WINDOW_ID" in os.environ:
            return "Kitty"

        # Alacritty
        if "ALACRITTY_SOCKET" in os.environ or "ALACRITTY_LOG" in os.environ:
            return "Alacritty"

        # VTE-based terminals (GNOME Terminal, Tilix, etc.)
        if "VTE_VERSION" in os.environ:
            return "VTE-based (GNOME Terminal/Tilix/etc.)"

        # Konsole
        if "KONSOLE_VERSION" in os.environ:
            return "Konsole"

        return "Unknown"

    @work(exit_on_error=False)
    async def capture_event(self, event_name: str, **properties: Any) -> None:
        """Capture an event.

        Args:
            event_name: Name of the event.
            **properties: Additional data associated with the event.
        """

        POSTHOG_API_KEY = "phc_mJWPV7GP3ar1i9vxBg2U8aiKsjNgVwum6F6ZggaD4ri"
        POSTHOG_HOST = "https://us.i.posthog.com"
        POSTHOG_EVENT_URL = f"{POSTHOG_HOST}/i/v0/e/"
        timestamp = datetime.now(timezone.utc).isoformat()
        width, height = self.size

        event_properties = {
            "toad_version": self.version,
            "term_program": self.term_program,
            "term_width": width,
            "term_height": height,
        } | properties
        body_json = {
            "api_key": POSTHOG_API_KEY,
            "event": event_name,
            "distinct_id": self.anon_id,
            "properties": event_properties,
            "timestamp": timestamp,
            "os": platform.system(),
        }
        if not self.settings.get("statistics.allow_collect", bool):
            # User has disabled stats
            return

        import httpx

        try:
            async with httpx.AsyncClient() as client:
                await client.post(POSTHOG_EVENT_URL, json=body_json)
        except Exception:
            pass

    @work(thread=True, exit_on_error=False)
    def system_notify(
        self, message: str, *, title: str = "", sound: str | None = None
    ) -> None:
        """Use OS level notifications.

        Args:
            message: Message to display.
            title: Title of the notificaiton.
            sound: filename (minus .wav) of a sound effect in the sounds/ directory.
        """
        system_notifications = self.settings.get("notifications.system", str)
        if not (
            system_notifications == "always"
            or (system_notifications == "blur" and not self.app_focus)
        ):
            return

        from notifypy import Notify

        notification = Notify()
        notification.message = message
        notification.title = title
        notification.application_name = "🐸 Toad" if toad.os == "macos" else "Toad"
        if sound and self.settings.get("notifications.enable_sounds", bool):
            sound_path = str(files("toad.data").joinpath(f"sounds/{sound}.wav"))
            notification.audio = sound_path

        icon_path = str(files("toad.data").joinpath("images/frog.png"))
        notification.icon = icon_path

        notification.send()

    def on_notify(self, event: Notify) -> None:
        """Handle notification message."""
        system_notifications = self.settings.get("notifications.system", str)
        if system_notifications == "always" or (
            system_notifications == "blur" and not self.app_focus
        ):
            hide_low_severity = self.settings.get(
                "notifications.hide_low_severity", bool
            )
            if event.notification.markup:
                # Strip content markup
                message = Content.from_markup(event.notification.message).plain
            else:
                message = event.notification.message
            if not (hide_low_severity and event.notification.severity == "information"):
                self.system_notify(message, title=event.notification.title)
        self._notifications.add(event.notification)
        self._refresh_notifications()

    def save_settings(self) -> None:
        if self.settings.changed:
            path = str(self.settings_path)
            try:
                atomic.write(path, self.settings.json)
            except Exception as error:
                self.notify(str(error), title="Settings", severity="error")
            else:
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
        elif key == "ui.compact-input":
            self.set_class(bool(value), "-compact-input")
        elif key == "ui.footer":
            self.set_class(not bool(value), "-hide-footer")
        elif key == "ui.status-line":
            self.set_class(not bool(value), "-hide-status-line")
        elif key == "ui.agent-title":
            self.set_class(not bool(value), "-hide-agent-title")
        elif key == "ui.info-bar":
            self.set_class(not bool(value), "-hide-info-bar")
        elif key == "agent.thoughts":
            self.set_class(not bool(value), "-hide-thoughts")
        elif key == "sidebar.hide":
            self.set_class(bool(value), "-hide-sidebar")

        self.settings_changed_signal.publish((key, value))

    async def on_load(self) -> None:
        db = await self.get_db()
        await db.create()
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

    async def on_mount(self) -> None:
        self.capture_event("toad-run")
        self.anon_id

        if mode := self._initial_mode:
            self.switch_mode(mode)
        else:
            self.push_screen(self.get_main_screen())

        self.update_terminal_title()
        self.set_timer(1, self.run_version_check)
        self.set_process_title()

    @work(thread=True, exit_on_error=False)
    def set_process_title(self) -> None:
        try:
            import setproctitle

            setproctitle.setproctitle("toad")
        except Exception:
            pass

    @on(events.TextSelected)
    async def on_text_selected(self) -> None:
        if self.settings.get("ui.auto_copy", bool):
            if (selection := self.screen.get_selected_text()) is not None:
                self.copy_to_clipboard(selection)
                self.notify(
                    "Copied selection to clipboard (see settings)",
                    title="Automatic copy",
                )

    def run_on_exit(self):
        if self.update_required and self.version_meta is not None:
            version_meta = self.version_meta
            from rich.console import Console
            from rich.panel import Panel

            console = Console()
            console.print(
                Panel(
                    version_meta.upgrade_message,
                    style="magenta",
                    border_style="bright_red",
                    title="🐸 Update available 🐸",
                    expand=False,
                    padding=(1, 4),
                )
            )
            console.print(f"Please visit {version_meta.visit_url}")

    @work(exit_on_error=False)
    async def run_version_check(self) -> None:
        """Check remote version."""
        from toad.version import check_version, VersionCheckFailed

        try:
            update_required, version_meta = await check_version()
        except VersionCheckFailed:
            return
        self.version_meta = version_meta
        self.update_required = update_required

    def get_main_screen(self) -> MainScreen:
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

    def action_toggle_help_panel(self):
        if self.screen.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()
