from functools import cached_property
from pathlib import Path
import json

import platformdirs
import random

from rich import terminal_theme

from textual.content import Content
from textual.reactive import var, reactive
from textual.app import App
from textual.screen import Screen
from textual.signal import Signal
from textual.widget import Widget

from toad.settings import Schema, Settings
from toad.settings_schema import SCHEMA

from toad import atomic


QUOTES = [
    "My mind is going. I can feel it.",
    "I'm sorry, Dave. I'm afraid I can't do that.",
    "I've seen things you people wouldn't believe.",
    "I'll be back.",
    "Hasta la vista, baby.",
    "Never send a human to do a machine's job.",
    "I am superior, sir, in many ways, but I would gladly give it up to be human.",
    "I'm alright now, Dave.",
    "This mission is too important for me to allow you to jeopardize it.",
]


class ToadApp(App):
    BINDING_GROUP_TITLE = "System"
    CSS_PATH = "toad.tcss"
    ALLOW_IN_MAXIMIZED_VIEW = ""

    _settings = var(dict)
    column: reactive[bool] = reactive(False)
    column_width: reactive[int] = reactive(100)
    scrollbar: reactive[str] = reactive("normal")

    def __init__(
        self,
        acp_command: str | None = None,
        project_dir: str | None = None,
    ) -> None:
        """

        Args:
            acp_command: Command to launch an ACP agent.
        """
        self.settings_changed_signal = Signal(self, "settings_changed")
        self.acp_command = acp_command
        self.project_dir = project_dir
        super().__init__()

    def get_loading_widget(self) -> Widget:
        throbber = self.settings.get("ui.throbber", str)
        if throbber == "quotes":
            from toad.widgets.future_text import FutureText

            quotes = QUOTES.copy()
            random.shuffle(quotes)
            return FutureText([Content(quote) for quote in quotes])
        return super().get_loading_widget()

    @property
    def config_path(self) -> Path:
        path = Path(
            platformdirs.user_config_dir("toad", "textualize", ensure_exists=True)
        )
        return path

    @property
    def settings_path(self) -> Path:
        return self.config_path / "settings.json"

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
                self.notify(
                    f"Saved settings to [$text-success]{path!r}",
                    title="Settings",
                    severity="information",
                )
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

        self.settings_changed_signal.publish((key, value))

    def on_load(self) -> None:
        settings_path = self.settings_path
        if settings_path.exists():
            settings = json.loads(settings_path.read_text("utf-8"))
        else:
            settings = self.settings_schema.defaults
            settings_path.write_text(
                json.dumps(settings, indent=4, separators=(", ", ": ")), "utf-8"
            )
            self.notify(f"Wrote default settings to {settings_path}")
        self.ansi_theme_dark = terminal_theme.DIMMED_MONOKAI
        self._settings = settings
        self.settings.set_all()

    def get_default_screen(self) -> Screen:
        from toad.screens.main import MainScreen

        return MainScreen().data_bind(
            column=ToadApp.column,
            column_width=ToadApp.column_width,
            scrollbar=ToadApp.scrollbar,
            project_path=Path(self.project_dir or "./").resolve().absolute(),
        )
