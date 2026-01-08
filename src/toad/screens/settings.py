from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual import lazy
from textual import containers
from textual.content import Content
from textual.screen import ModalScreen, ScreenResultType
from textual.widgets import Input, Select, Checkbox, Footer, Static, TextArea
from textual.compose import compose
from textual.validation import Validator, Number
from textual import getters


from toad.settings import Setting
from toad.app import ToadApp


class SettingsInput(Input):
    pass


class SettingsScreen(ModalScreen):
    BINDINGS = [
        ("escape", "dismiss", "Dismiss settings"),
        ("ctrl+s", "screen.focus('#search')", "Focus search"),
    ]
    CSS_PATH = "settings.tcss"

    app = getters.app(ToadApp)

    search_input = getters.query_one("Input#search", Input)

    AUTO_FOCUS = "Input#search"

    def compose(self) -> ComposeResult:
        settings = self.app.settings
        schema = self.app.settings_schema

        def schema_to_widget(
            group_title: str, settings_map: dict[str, Setting]
        ) -> ComposeResult:
            for _key, setting in settings_map.items():
                if not setting.editable:
                    continue
                if setting.type == "object":
                    if setting.children is not None:
                        with containers.VerticalGroup(classes="setting-object"):
                            with containers.VerticalGroup(classes="heading"):
                                yield Static(setting.title, classes="title")
                                yield Static(setting.help, classes="help")
                            with containers.VerticalGroup(
                                id="setting-group", classes="setting-group"
                            ):
                                yield from compose(
                                    self,
                                    schema_to_widget(setting.title, setting.children),
                                )

                else:
                    with containers.VerticalGroup(
                        classes="setting",
                        name=f"{group_title.lower()} {setting.title.lower()}",
                    ):
                        value = settings.get(setting.key, object, expand=False)
                        default = settings.schema.get_default(setting.key)

                        if setting.type == "text" or default is None:
                            help = Content.from_markup(setting.help)
                        else:
                            if setting.type == "choices":
                                # For choices we need to translate the default to its associated label
                                choices = setting.choices or []
                                for choice in choices:
                                    if isinstance(choice, tuple):
                                        title, choice_value = choice
                                    else:
                                        title = choice_value = choice
                                    if default == choice_value:
                                        default = title
                                else:
                                    help = Content()

                            if setting.help:
                                help = Content.assemble(
                                    Content.from_markup(setting.help),
                                    (f"\ndefault: {default!r}", "$text-secondary"),
                                )
                            else:
                                help = Content.styled(
                                    f"default: {default!r}", "$text-secondary"
                                )

                        yield Static(setting.title, classes="title")
                        if help:
                            yield Static(help, classes="help")
                        if setting.type == "string":
                            with self.prevent(Input.Changed):
                                yield Input(
                                    str(value), classes="input", name=setting.key
                                )
                        if setting.type == "text":
                            # with self.prevent(TextArea.Changed):
                            yield TextArea(
                                str(value), classes="input", name=setting.key
                            )
                        elif setting.type == "boolean":
                            with self.prevent(Checkbox.Changed):
                                yield Checkbox(
                                    value=bool(value),
                                    classes="input",
                                    name=setting.key,
                                )
                        elif setting.type == "integer":
                            try:
                                integer_value = int(value)
                            except (ValueError, TypeError):
                                integer_value = setting.default
                            setting_validate = setting.validate or []
                            validators: list[Validator] = []
                            for validate in setting_validate:
                                validate_type = validate["type"]
                                if validate_type == "minimum":
                                    validators.append(Number(minimum=validate["value"]))
                                elif validate_type == "maximum":
                                    validators.append(Number(maximum=validate["value"]))
                            with self.prevent(Input.Changed):
                                yield Input(
                                    str(integer_value),
                                    type="integer",
                                    classes="input",
                                    name=setting.key,
                                    validators=validators,
                                )
                        elif setting.type == "number":
                            try:
                                integer_value = float(value)
                            except (ValueError, TypeError):
                                integer_value = setting.default
                            setting_validate = setting.validate or []
                            validators: list[Validator] = []
                            for validate in setting_validate:
                                validate_type = validate["type"]
                                if validate_type == "minimum":
                                    validators.append(Number(minimum=validate["value"]))
                                elif validate_type == "maximum":
                                    validators.append(Number(maximum=validate["value"]))
                            with self.prevent(Input.Changed):
                                yield Input(
                                    str(integer_value),
                                    type="number",
                                    classes="input",
                                    name=setting.key,
                                    validators=validators,
                                )
                        elif setting.type == "choices":
                            select_value = str(value)
                            choices = setting.choices or []
                            with self.prevent(Select.Changed):
                                select_choices = [
                                    (
                                        choice
                                        if isinstance(choice, tuple)
                                        else (choice, choice)
                                    )
                                    for choice in choices
                                ]
                                choices_set = {choice[1] for choice in select_choices}
                                yield Select(
                                    select_choices,
                                    value=(
                                        select_value
                                        if select_value in choices_set
                                        else setting.default
                                    ),
                                    classes="input",
                                    name=setting.key,
                                    allow_blank=setting.default is None,
                                )

        with containers.Vertical(id="contents"):
            with containers.VerticalGroup(classes="search-container"):
                yield Input(id="search", placeholder="Search settings")
            with lazy.Reveal(
                containers.VerticalScroll(can_focus=False, id="settings-container")
            ):
                yield from compose(self, schema_to_widget("", schema.settings_map))

        yield Footer()

    @on(Input.Blurred, "Input")
    @on(Input.Submitted, "Input")
    def on_input_blurred(self, event: Input.Blurred) -> None:
        if event.validation_result and not event.validation_result.is_valid:
            self.notify(
                event.validation_result.failures[0].description or "error",
                title=event.input.name or "",
                severity="error",
            )
            event.input.value = str(
                self.app.settings.get(event.input.name or "", expand=False)
            )
            return
        if event.input.name is not None:
            if event.input.type == "integer":
                self.app.settings.set(event.input.name, int(event.value or "0"))
            elif event.input.type == "number":
                self.app.settings.set(event.input.name, float(event.value or "0"))
            else:
                self.app.settings.set(event.input.name, event.value)

    @on(TextArea.Changed)
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.name is not None:
            self.app.settings.set(event.text_area.name, event.text_area.text)

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.name is not None:
            self.app.settings.set(event.checkbox.name, event.checkbox.value)

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.name is not None:
            self.app.settings.set(event.select.name, event.select.value)

    def filter_settings(self, search_term: str) -> None:
        if search_term:
            search_term = search_term.lower()
            for setting in self.query(".setting"):
                if setting.name:
                    setting.display = search_term in setting.name
            for container in reversed(self.query(".setting-object")):
                container.display = not container.get_child_by_id(
                    "setting-group"
                ).is_empty
        else:
            self.query(".setting").set(display=True)
            self.query(".setting-object").set(display=True)

    @on(Input.Changed, "#search")
    def on_search_input(self, event: Input.Changed) -> None:
        self.filter_settings(event.value)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "focus":
            if not self.is_mounted:
                return None
            return None if self.search_input.has_focus else True
        return True

    async def action_dismiss(self, result: ScreenResultType | None = None) -> None:
        self.query("#search").focus()
        self.call_after_refresh(self.dismiss, result)
