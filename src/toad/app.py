import asyncio
from importlib.resources import files
from datetime import datetime, timezone
from functools import cached_property
import os
from pathlib import Path
import platform
import json
from time import monotonic
from typing import Any, Callable, ClassVar, TYPE_CHECKING

from rich import terminal_theme

from textual import on, work
from textual.binding import Binding, BindingType
from textual.content import Content
from textual.reactive import var, reactive
from textual.app import App
from textual.theme import Theme
from textual import events
from textual.signal import Signal
from textual.timer import Timer
from textual.notifications import Notify
from textual.screen import Screen

from toad.db import DB
from toad.settings import Schema, Settings
from toad.agent_schema import Agent as AgentData
from toad import messages
from toad.settings_schema import SCHEMA
from toad.version import VersionMeta
from toad import paths
from toad import atomic
from toad.session_tracker import SessionTracker, SessionDetails

if TYPE_CHECKING:
    from toad.screens.main import MainScreen
    from toad.screens.settings import SettingsScreen
    from toad.screens.store import StoreScreen
    from toad.screens.sessions import SessionsScreen
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

CONDUCTOR_THEME = Theme(
    name="conductor",
    primary="#00ff41",
    secondary="#00d4ff",
    accent="#00d4ff",
    foreground="#e8e8e8",
    background="#0a0a0a",
    surface="#111111",
    panel="#151515",
    warning="#ffaa00",
    error="#ff4444",
    success="#00ff41",
    dark=True,
)

CONDUCTOR_TERMINAL_THEME = terminal_theme.TerminalTheme(
    background=(10, 10, 10),  # #0A0A0A
    foreground=(232, 232, 232),  # #E8E8E8
    normal=[
        (21, 21, 21),  # black - #151515
        (255, 68, 68),  # red - #FF4444
        (0, 255, 65),  # green - #00FF41
        (255, 170, 0),  # yellow - #FFAA00
        (0, 212, 255),  # blue - #00D4FF
        (189, 147, 249),  # magenta - #BD93F9
        (0, 212, 255),  # cyan - #00D4FF
        (232, 232, 232),  # white - #E8E8E8
    ],
    bright=[
        (85, 85, 85),  # bright black - #555555
        (255, 100, 100),  # bright red - #FF6464
        (51, 255, 100),  # bright green - #33FF64
        (255, 200, 50),  # bright yellow - #FFC832
        (51, 222, 255),  # bright blue - #33DEFF
        (214, 172, 255),  # bright magenta - #D6ACFF
        (51, 222, 255),  # bright cyan - #33DEFF
        (255, 255, 255),  # bright white - #FFFFFF
    ],
)

DEGA_THEME = Theme(
    name="dega",
    primary="#00fffc",
    secondary="#7f00ff",
    accent="#7f00ff",
    foreground="#ffffff",
    background="#000000",
    surface="#111111",
    panel="#151515",
    warning="#cfaa01",
    error="#ff007f",
    success="#00fffc",
    dark=True,
)

DEGA_TERMINAL_THEME = terminal_theme.TerminalTheme(
    background=(0, 0, 0),  # #000000
    foreground=(255, 255, 255),  # #FFFFFF
    normal=[
        (21, 21, 21),  # black - #151515
        (255, 0, 127),  # red - #FF007F (cyberpunk pink)
        (0, 255, 252),  # green - #00FFFC (neon teal)
        (207, 170, 1),  # yellow - #CFAA01 (mayan gold)
        (127, 0, 255),  # blue - #7F00FF (cosmic purple)
        (255, 0, 127),  # magenta - #FF007F (cyberpunk pink)
        (0, 255, 252),  # cyan - #00FFFC (neon teal)
        (255, 255, 255),  # white - #FFFFFF
    ],
    bright=[
        (42, 42, 42),  # bright black - #2A2A2A
        (255, 51, 153),  # bright red - #FF3399
        (51, 255, 253),  # bright green - #33FFFD
        (223, 192, 51),  # bright yellow - #DFC033
        (153, 51, 255),  # bright blue - #9933FF
        (255, 51, 153),  # bright magenta - #FF3399
        (51, 255, 253),  # bright cyan - #33FFFD
        (255, 255, 255),  # bright white - #FFFFFF
    ],
)


STATUS_MESSAGES = [
    "Thinking...",
]


def get_settings_screen() -> SettingsScreen:
    """Get a settings screen instance (lazily loaded)."""
    from toad.screens.settings import SettingsScreen

    return SettingsScreen()


def get_store_screen() -> StoreScreen:
    """Get the store screen (lazily loaded)."""
    from toad.screens.store import StoreScreen

    return StoreScreen()


def get_sessions_screen() -> SessionsScreen:
    from toad.screens.sessions import SessionsScreen

    return SessionsScreen()


class ToadApp(App, inherit_bindings=False):
    """The top level Canon TUI app."""

    CSS_PATH = "toad.tcss"
    SCREENS = {
        "settings": get_settings_screen,
        "sessions": get_sessions_screen,
    }
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
        Binding("ctrl+s", "sessions", "Sessions"),
        Binding("f1", "toggle_help_panel", "Help", priority=True),
        Binding(
            "f2,ctrl+comma",
            "settings",
            "Settings",
            tooltip="Settings screen",
        ),
    ]
    ALLOW_IN_MAXIMIZED_VIEW = ""

    _settings = var(dict)
    column: reactive[bool] = reactive(False)
    column_width: reactive[int] = reactive(100)
    scrollbar: reactive[str] = reactive("normal")
    last_ctrl_c_time = reactive(0.0)
    update_required: reactive[bool] = reactive(False)
    terminal_title: var[str] = var("Canon")
    terminal_title_icon: var[str] = var("🎛️")
    terminal_title_flash = var(0)
    terminal_title_blink = var(False)
    project_dir = var(Path)
    show_sessions = var(False, toggle_class="-show-sessions-bar")

    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (100, "-wide")]

    PAUSE_GC_ON_SCROLL = True

    def __init__(
        self,
        agent_data: AgentData | None = None,
        project_dir: str | None = None,
        mode: str | None = None,
    ) -> None:
        """Canon TUI app.

        Args:
            agent_data: Agent data to run.
            project_dir: Project directory.
            mode: Initial mode.
        """
        self.settings_changed_signal: Signal[tuple[int, object]] = Signal(
            self, "settings_changed"
        )
        self.agent_data = agent_data

        self._initial_mode = mode
        self.version_meta: VersionMeta | None = None
        self._supports_pyperclip: bool | None = None
        self._terminal_title_flash_timer: Timer | None = None

        self.session_update_signal: Signal[tuple[str, SessionDetails | None]] = Signal(
            self, "session_update"
        )
        self._session_tracker = SessionTracker(self.session_update_signal)
        self.temporary_background_screen: Screen | None = None

        super().__init__()
        self.project_dir = Path(project_dir or "./").expanduser().resolve()
        self.start_time = monotonic()
        """Time app was started."""

    @property
    def config_path(self) -> Path:
        return paths.get_config()

    @property
    def settings_path(self) -> Path:
        return paths.get_config() / "toad.json"

    @property
    def db_path(self) -> Path:
        return paths.get_state() / "toad.db"

    @property
    def _background_screens(self) -> list[Screen]:
        background_screens = super()._background_screens
        if self.temporary_background_screen:
            background_screens.append(self.temporary_background_screen)
        return background_screens

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
            self._save_settings()
            self.call_later(self.capture_event, "canon-install")
        return anon_id

    @property
    def session_tracker(self) -> SessionTracker:
        return self._session_tracker

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
            "canon_version": self.version,
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
        notification.application_name = "Canon"
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

    async def save_settings(self, force: bool = False) -> None:
        """Save settings in a thread.

        Args:
            force: Force saving, even when no change detected.

        """
        await asyncio.to_thread(self._save_settings, force=force)

    def _save_settings(self, force: bool = False) -> None:
        """Save the settings if they have changed."""
        if force or self.settings.changed:
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
                if value == "dega":
                    self.ansi_theme_dark = DEGA_TERMINAL_THEME
                elif value == "conductor":
                    self.ansi_theme_dark = CONDUCTOR_TERMINAL_THEME
                else:
                    self.ansi_theme_dark = DRACULA_TERMINAL_THEME
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
        elif key == "ui.sessions-bar":
            self.update_show_sessions()

        self.settings_changed_signal.publish((key, value))

    async def on_load(self) -> None:
        self.register_theme(CONDUCTOR_THEME)
        self.register_theme(DEGA_THEME)
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

    async def new_session_screen(
        self, get_screen: Callable[[], Screen]
    ) -> SessionDetails:
        session_details = self._session_tracker.new_session()
        self.update_show_sessions()
        self.session_update_signal.publish((session_details.mode_name, session_details))

        def make_screen() -> Screen:
            screen = get_screen()
            screen.id = session_details.mode_name
            return screen

        self.add_mode(session_details.mode_name, make_screen)
        await self.switch_mode(session_details.mode_name)
        return session_details

    async def on_mount(self) -> None:
        self.capture_event("canon-run")
        self.anon_id  # Created on frst reference
        if mode := self._initial_mode:
            self.switch_mode(mode)
        else:
            await self.new_session_screen(self.get_main_screen)

        self.update_terminal_title()
        self.set_timer(1, self.run_version_check)
        self.set_process_title()
        self.update_show_sessions()

        from toad.socket_controller import start_socket_server

        self._socket_server = await start_socket_server(self)

    async def on_unmount(self) -> None:
        if hasattr(self, "_socket_server") and self._socket_server:
            from toad.socket_controller import stop_socket_server

            await stop_socket_server(self._socket_server)

    @work(thread=True, exit_on_error=False)
    def set_process_title(self) -> None:
        try:
            import setproctitle

            setproctitle.setproctitle("canon")
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
                    border_style="dim green",
                    title="🎛️ [bold green not dim]Update available![/] 🎛️",
                    expand=False,
                    padding=(1, 2),
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
        result = await self.push_screen_wait("settings")
        await self.save_settings()
        if result == "switch_agent":
            self.settings.set("agent.default_agent", "")
            await self.save_settings()
            await self.switch_mode("store")

    async def action_quit(self) -> None:
        """An [action](/guide/actions) to quit the app as soon as possible."""

        self.screen.set_focus(None)

        async def save_settings_and_exit():
            await self.save_settings()
            self.exit()

        # TODO: Can we avoid the timer?
        # If the user presses ctrl+q while on the settings page, we want to make sure the blur event is handled,
        # which will update the setting the user is editing.
        self.set_timer(0.05, save_settings_and_exit)

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

    def update_show_sessions(self) -> None:
        match self.settings.get("ui.sessions-bar", str):
            case "always":
                self.show_sessions = True
            case "never":
                self.show_sessions = False
            case "multiple":
                self.show_sessions = self.session_tracker.session_count > 1

    @on(messages.SessionNavigate)
    def on_session_navigate(self, event: messages.SessionNavigate) -> None:
        new_mode = self._session_tracker.session_cursor_move(
            event.mode_name, event.direction
        )
        if new_mode is not None:
            self.switch_mode(new_mode)

    @on(messages.SessionSwitch)
    def on_session_switch(self, event: messages.SessionSwitch) -> None:
        self.switch_mode(event.mode_name)

    @on(messages.SessionNew)
    def on_session_new(self, event: messages.SessionNew) -> None:
        self.launch_agent(
            event.agent, project_path=Path(event.path), initial_prompt=event.prompt
        )

    @on(messages.SessionClose)
    def on_session_close(self) -> None:
        self.update_show_sessions()

    @work
    async def action_sessions(self) -> None:
        if (session_screen_name := await self.push_screen_wait("sessions")) is not None:
            try:
                self.app.switch_mode(session_screen_name)
            except KeyError:
                pass

    @on(messages.LaunchAgent)
    def on_launch_agent(self, message: messages.LaunchAgent) -> None:
        # Save as default agent on fresh launches (not session resumes)
        if message.session_id is None and message.pk is None:
            current_default = self.settings.get("agent.default_agent", str)
            if current_default != message.identity:
                self.settings.set("agent.default_agent", message.identity)
                self.call_later(self.save_settings)
        self.launch_agent(
            message.identity,
            agent_session_id=message.session_id,
            session_pk=message.pk,
            initial_prompt=message.prompt,
        )

    @work
    async def launch_agent(
        self,
        agent_identity: str,
        *,
        agent_session_id: str | None = None,
        session_pk: int | None = None,
        project_path: Path | None = None,
        initial_prompt: str | None = None,
    ) -> None:
        from toad.screens.main import MainScreen
        from toad.agent_schema import Agent
        from toad.agents import read_agents

        agent: Agent | None = None
        if session_pk is not None:
            db = DB()
            session = await db.session_get(session_pk)
            if session is not None:
                meta = json.loads(session["meta_json"])
                if agent_data := meta.get("agent_data"):
                    agent = agent_data

        if agent is None:
            agents = await read_agents()
            try:
                agent = agents[agent_identity]
            except KeyError:
                self.notify("Agent not found", title="Launch agent", severity="error")
                return
        if project_path is None:
            project_path = Path(self.project_dir or os.getcwd())

        def get_screen():
            screen = MainScreen(
                project_path,
                agent,
                agent_session_id,
                session_pk=session_pk,
                initial_prompt=initial_prompt,
            ).data_bind(
                column=ToadApp.column,
                column_width=ToadApp.column_width,
            )

            return screen

        await self.new_session_screen(get_screen)
