from dataclasses import dataclass
from operator import itemgetter
from typing import Iterable, Self, Sequence

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.content import Content, Span

from textual import getters
from textual.message import Message
from textual.reactive import var
from textual import containers
from textual import widgets
from textual.widgets.option_list import Option

from toad.fuzzy import FuzzySearch
from toad.messages import Dismiss
from toad.slash_command import SlashCommand
from toad.visuals.columns import Columns


class SlashCompleteInput(widgets.Input):
    BINDING_GROUP_TITLE = "Fuzzy search slash commands"
    HELP = """\
## Slash command fuzzy search

Search for slash commands by typing a few characters from the command.

- **cursor keys** Navigate list
- **enter** Add command to prompt
- **escape** Dismiss fuzzy search
"""


class SlashComplete(containers.VerticalGroup):
    """A widget to auto-complete slash commands."""

    CURSOR_BINDING_GROUP = Binding.Group(description="Select")
    BINDINGS = [
        Binding(
            "up",
            "cursor_up",
            "Cursor up",
            group=CURSOR_BINDING_GROUP,
            priority=True,
        ),
        Binding(
            "down",
            "cursor_down",
            "Cursor down",
            group=CURSOR_BINDING_GROUP,
            priority=True,
        ),
        Binding("enter", "submit", "Insert /command", priority=True),
        Binding("escape", "dismiss", "Dismiss", priority=True),
    ]

    DEFAULT_CSS = """
    SlashComplete {
        OptionList {
            height: auto;
        }
    }
    """

    input = getters.query_one(widgets.Input)
    option_list = getters.query_one(widgets.OptionList)

    slash_commands: var[list[SlashCommand]] = var(list)

    @dataclass
    class Completed(Message):
        command: str

    def __init__(
        self,
        slash_commands: Iterable[SlashCommand] | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.slash_commands = list(slash_commands) if slash_commands else []
        self.hints = {
            slash_command.command: slash_command.hint
            for slash_command in self.slash_commands
            if slash_command.hint
        }

        self.fuzzy_search = FuzzySearch(case_sensitive=False)

    def compose(self) -> ComposeResult:
        yield SlashCompleteInput(compact=True, placeholder="fuzzy search")
        yield widgets.OptionList()

    def focus(self, scroll_visible: bool = False) -> Self:
        self.filter_slash_commands("")
        self.input.focus(scroll_visible)
        return self

    def on_mount(self) -> None:
        self.filter_slash_commands("")

    def on_descendant_blur(self) -> None:
        self.post_message(Dismiss(self))

    @on(widgets.Input.Changed)
    def on_input_changed(self, event: widgets.Input.Changed) -> None:
        event.stop()
        self.filter_slash_commands(event.value)

    async def watch_slash_commands(self, slash_commands: list[SlashCommand]) -> None:
        self.hints = {
            slash_command.command: slash_command.hint
            for slash_command in slash_commands
            if slash_command.hint
        }
        self.filter_slash_commands(self.input.value)

    def filter_slash_commands(self, prompt: str) -> None:
        """Filter slash commands by the given prompt.

        Args:
            prompt: Text prompt.
        """
        prompt = prompt.lstrip("/").casefold().rstrip()
        columns = self.columns = Columns("auto", "flex")

        slash_commands = sorted(
            self.slash_commands,
            key=lambda slash_command: slash_command.command.casefold(),
        )
        deduplicated_slash_commands = {
            slash_command.command: slash_command for slash_command in slash_commands
        }
        self.fuzzy_search.cache.grow(len(deduplicated_slash_commands))

        if prompt:
            slash_prompt = f"/{prompt}"
            scores: list[tuple[float, Sequence[int], SlashCommand]] = [
                (
                    *self.fuzzy_search.match(prompt, slash_command.command[1:]),
                    slash_command,
                )
                for slash_command in slash_commands
            ]

            scores = sorted(
                [
                    (
                        (
                            score * 2
                            if slash_command.command.casefold().startswith(slash_prompt)
                            else score
                        ),
                        highlights,
                        slash_command,
                    )
                    for score, highlights, slash_command in scores
                    if score
                ],
                key=itemgetter(0),
                reverse=True,
            )
        else:
            scores = [(1.0, [], slash_command) for slash_command in slash_commands]

        def make_row(
            slash_command: SlashCommand, indices: Iterable[int]
        ) -> tuple[Content, ...]:
            """Make a row for the Columns display.

            Args:
                slash_command: The slash command instance.
                indices: Indices of matching characters.

            Returns:
                A tuple of `Content` instances for use as a column row.
            """
            command = Content.styled(slash_command.command, "$text-success")
            command = command.add_spans(
                [Span(index + 1, index + 2, "underline not dim") for index in indices]
            )
            return (command, Content.styled(slash_command.help, "dim"))

        rows = [
            (
                columns.add_row(
                    *make_row(slash_command, indices),
                ),
                slash_command.command,
            )
            for _, indices, slash_command in scores
        ]
        self.option_list.set_options(
            Option(row, id=command_name) for row, command_name in rows
        )
        if self.display:
            self.option_list.highlighted = 0
        else:
            with self.option_list.prevent(widgets.OptionList.OptionHighlighted):
                self.option_list.highlighted = 0

    def action_cursor_down(self) -> None:
        self.option_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        self.option_list.action_cursor_up()

    def action_dismiss(self) -> None:
        self.post_message(Dismiss(self))

    def action_submit(self) -> None:
        option_list = self.option_list
        if (option := option_list.highlighted_option) is not None:
            with self.input.prevent(widgets.Input.Changed):
                self.input.clear()
            self.post_message(self.Completed(option.id or ""))


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    COMMANDS = [
        SlashCommand("/help", "Help with slash commands"),
        SlashCommand("/foo", "This is FOO"),
        SlashCommand("/bar", "This is BAR"),
        SlashCommand("/baz", "This is BAZ"),
    ]

    class SlashApp(App):
        def compose(self) -> ComposeResult:
            yield SlashComplete(COMMANDS)

    SlashApp().run()
