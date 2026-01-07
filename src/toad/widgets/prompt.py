from pathlib import Path
import shlex
from typing import Callable, Literal, Self

from textual import on
from textual.reactive import var, Initialize
from textual.app import ComposeResult

from textual.actions import SkipAction
from textual.binding import Binding

from textual.content import Content
from textual import getters
from textual.message import Message
from textual.widgets import OptionList, TextArea, Label
from textual import containers
from textual.widget import Widget
from textual.widgets.option_list import Option
from textual.widgets.text_area import Selection
from textual import events

from toad.app import ToadApp
from toad import messages
from toad.widgets.highlighted_textarea import HighlightedTextArea
from toad.widgets.condensed_path import CondensedPath
from toad.widgets.path_search import PathSearch
from toad.widgets.plan import Plan
from toad.widgets.question import Ask, Question
from toad.widgets.slash_complete import SlashComplete
from toad.messages import UserInputSubmitted
from toad.slash_command import SlashCommand
from toad.prompt.extract import extract_paths_from_prompt
from toad.acp.agent import Mode
from toad.path_complete import PathComplete


class ModeSwitcher(OptionList):
    BINDINGS = [Binding("escape", "dismiss")]

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected):
        self.post_message(messages.ChangeMode(event.option_id))
        self.blur()

    def action_dismiss(self):
        self.blur()


class InvokeFileSearch(Message):
    pass


class InvokeSlashComplete(Message):
    pass


class AgentInfo(Label):
    pass


class ModeInfo(Label):
    pass


class StatusLine(Label):
    status: var[str] = var("")

    def watch_status(self, status: str) -> None:
        self.set_class(not bool(status), "-hidden")
        self.update(status)
        self.tooltip = status


class PromptContainer(containers.HorizontalGroup):
    def on_mouse_down(self, event: events.MouseUp) -> None:
        for child in self.query("*"):
            if child.has_focus:
                return
        prompt_text_area = self.query_one(PromptTextArea)
        if not prompt_text_area.has_focus:
            prompt_text_area.focus()


class PromptTextArea(HighlightedTextArea):
    BINDING_GROUP_TITLE = "Prompt"

    BINDINGS = [
        Binding(
            "enter",
            "submit",
            "Send",
            key_display="⏎",
            priority=True,
            tooltip="Send the prompt to the agent",
        ),
        Binding(
            "ctrl+j,shift+enter",
            "newline",
            "Line",
            key_display="⇧+⏎",
            tooltip="Insert a new line character",
        ),
        Binding(
            "ctrl+j,shift+enter",
            "multiline_submit",
            "Send",
            key_display="⇧+⏎",
            tooltip="Send the prompt to the agent",
        ),
        Binding(
            "tab",
            "tab_complete",
            "Complete",
            tooltip="Complete path (if possible)",
            priority=True,
            show=False,
        ),
    ]

    app = getters.app(ToadApp)

    auto_completes: var[list[Option]] = var(list)
    multi_line = var(False, bindings=True)
    shell_mode = var(False, bindings=True)
    agent_ready: var[bool] = var(False)
    path_complete: var[PathComplete] = var(Initialize(lambda obj: PathComplete()))
    suggestions: var[list[str] | None] = var(None)
    suggestions_index: var[int] = var(0)

    project_path = var(Path())
    working_directory = var("")

    slash_commands: var[list[SlashCommand]] = var([])
    slash_command_prefixes: var[tuple[str, ...]] = var(())

    class Submitted(Message):
        def __init__(self, markdown: str) -> None:
            self.markdown = markdown
            super().__init__()

    class RequestShellMode(Message):
        pass

    class CancelShell(Message):
        pass

    def watch_slash_commands(self, slash_commands: list[SlashCommand]) -> None:
        """A tuple of slash commands for performance reasons (used with `str.startswith`)."""
        self.slash_command_prefixes = tuple(
            [slash_command.command for slash_command in slash_commands]
        )

    def highlight_slash_command(self, text: str) -> Content:
        """Override slash command highlighting."""

        if text.startswith(self.slash_command_prefixes):
            content = Content(text)
            for slash_command in self.slash_commands:
                if text.startswith(slash_command.command + " "):
                    content = content.stylize(
                        "$text-success", 0, len(slash_command.command)
                    )
                    break
            return content
        return Content(text)

    def highlight_shell(self, text: str) -> Content:
        """Override shell highlighting with additional danger detection."""
        content = super().highlight_shell(text)

        if not self.app.settings.get("shell.warn_dangerous", bool):
            return content

        from toad import danger

        spans, _danger_level = danger.detect(
            str(self.project_path), self.working_directory, content.plain
        )
        content = content.add_spans(spans)
        return content

    def on_mount(self) -> None:
        self.highlight_cursor_line = False
        self.hide_suggestion_on_blur = False

    def on_key(self, event: events.Key) -> None:
        if (
            not self.shell_mode
            and self.cursor_location == (0, 0)
            and event.character in {"!", "$"}
        ):
            self.post_message(self.RequestShellMode())
            event.prevent_default()
        elif self.shell_mode and event.key == "tab":
            event.prevent_default()
        else:
            self.suggestions = None
            self.suggestion = ""

    def update_suggestion(self) -> None:
        prompt = self.query_ancestor(Prompt)

        if self.selection.start == self.selection.end and self.text.startswith("/"):
            return

        if self.shell_mode and self.cursor_at_end_of_text and "\n" not in self.text:
            if prompt.complete_callback is not None:
                if completes := prompt.complete_callback(self.text):
                    self.suggestion = completes[-1]

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "newline" and self.multi_line:
            return False
        if action == "submit" and self.multi_line:
            return False
        if action == "multiline_submit":
            return self.multi_line
        return True

    def action_multiline_submit(self) -> None:
        if not self.agent_ready:
            self.app.bell()
            self.post_message(
                messages.Flash(
                    "Agent is not ready. Please wait while the agent connects…",
                    "warning",
                )
            )
            return
        self.post_message(UserInputSubmitted(self.text, self.shell_mode))
        self.clear()

    def action_newline(self) -> None:
        self.insert("\n")

    def action_submit(self) -> None:
        if not self.agent_ready and not self.shell_mode:
            self.app.bell()
            self.post_message(
                messages.Flash(
                    "Agent is not ready. Please wait while the agent connects…",
                    "warning",
                )
            )
            return
        if self.suggestion:
            if " " not in self.text:
                self.insert(self.suggestion + " ")
            else:
                prompt = self.query_ancestor(Prompt)
                last_token = shlex.split(self.text + self.suggestion)[-1]
                last_token_path = Path(prompt.working_directory) / last_token
                if last_token_path.is_dir():
                    self.insert(self.suggestion)
                else:
                    self.insert(self.suggestion + " ")
                self.suggestion = ""
            return
        self.post_message(UserInputSubmitted(self.text, self.shell_mode))
        self.clear()

    def action_cursor_up(self, select: bool = False):
        if self.selection.is_empty and not select:
            row, _column = self.selection[0]
            if row == 0:
                self.post_message(messages.HistoryMove(-1, self.shell_mode, self.text))
                return
        super().action_cursor_up(select)

    def action_cursor_down(self, select: bool = False):
        if self.selection.is_empty and not select:
            row, _column = self.selection[0]
            if row == (self.wrapped_document.height - 1):
                self.post_message(messages.HistoryMove(+1, self.shell_mode, self.text))
                return
        super().action_cursor_down(select)

    def action_delete_left(self) -> None:
        selection = self.selection
        if selection.start == selection.end and self.selection.end == (0, 0):
            self.post_message(self.CancelShell())
            return
        return super().action_delete_left()

    async def action_tab_complete(self) -> None:
        if not self.shell_mode:
            return

        import shlex

        prompt = self.query_ancestor(Prompt)

        if not self.cursor_at_end_of_text:
            return

        _cursor_row, cursor_column = prompt.prompt_text_area.selection.end
        pre_complete = self.text[:cursor_column]
        post_complete = self.text[cursor_column:]
        shlex_tokens = shlex.split(pre_complete)
        if not shlex_tokens:
            return

        command = shlex_tokens[0]

        exclude_node_type: Literal["file"] | Literal["dir"] | None = None
        if (
            command
            in self.app.settings.get("shell.directory_commands", str).splitlines()
        ):
            exclude_node_type = "file"
        elif command in self.app.settings.get("shell.file_commands", str).splitlines():
            exclude_node_type = "dir"

        tab_complete, suggestions = await self.path_complete(
            Path(prompt.working_directory),
            shlex_tokens[-1],
            exclude_type=exclude_node_type,
        )

        if tab_complete is not None:
            shlex_tokens = shlex_tokens[:-1] + [shlex_tokens[-1] + tab_complete]
            path_component = Path(prompt.working_directory) / shlex_tokens[-1]
            if path_component.is_file():
                spaces = " "
            else:
                spaces = ""

            self.clear()
            self.insert(
                " ".join(token.replace(" ", "\\ ") for token in shlex_tokens)
                + post_complete
                + spaces
            )
            self.suggestions = None
        else:
            if suggestions != self.suggestions:
                self.suggestions = suggestions or None
                self.suggestions_index = 0
                if suggestions:
                    self.suggestion = suggestions[0]
            elif self.suggestions:
                self.suggestions_index = (self.suggestions_index + 1) % len(
                    self.suggestions
                )
                self.suggestion = self.suggestions[self.suggestions_index]

    async def watch_selection(
        self, previous_selection: Selection, selection: Selection
    ) -> None:
        if previous_selection == selection:
            return
        if selection.start == selection.end:
            previous_y, previous_x = previous_selection.end
            y, x = selection.end
            if y == previous_y:
                direction = -1 if x < previous_x else +1
            else:
                direction = 0
            line = self.document.get_line(y)

            if (
                not self.shell_mode
                and y == 0
                and x == 1
                and direction == +1
                and line
                and line[0] == "/"
            ):
                self.post_message(InvokeSlashComplete())
                return

            if y == 0 and line and line[0] == "/" and direction == -1:
                if line in self.slash_command_prefixes:
                    self.selection = Selection((0, 0), (0, len(line)))
                    return

            for _path, start, end in extract_paths_from_prompt(line):
                if x > start and x < end:
                    self.selection = Selection((y, start), (y, end))
                    break
                if direction == -1 and x == end:
                    self.selection = Selection((y, start), (y, end))
                    break

            if x > 0 and x <= len(line) and line[x - 1] == "@":
                remaining_line = line[x + 1 :]
                if not remaining_line or remaining_line[0].isspace():
                    self.post_message(InvokeFileSearch())


class Prompt(containers.VerticalGroup):
    BINDINGS = [
        Binding("escape", "dismiss", "Dismiss"),
    ]

    PROMPT_NULL = " "
    PROMPT_SHELL = Content.styled("$", "$text-primary")
    PROMPT_AI = Content.styled("❯", "$text-secondary")
    PROMPT_MULTILINE = Content.styled("☰", "$text-secondary")

    prompt_container = getters.query_one("#prompt-container", Widget)
    prompt_text_area = getters.query_one(PromptTextArea)
    prompt_label = getters.query_one("#prompt", Label)
    current_directory = getters.query_one(CondensedPath)
    path_search = getters.query_one(PathSearch)
    slash_complete = getters.query_one(SlashComplete)
    question = getters.query_one(Question)
    mode_switcher = getters.query_one(ModeSwitcher)

    slash_commands: var[list[SlashCommand]] = var(list)
    shell_mode = var(False)
    multi_line = var(False)
    show_path_search = var(False, toggle_class="-show-path-search", bindings=True)
    show_slash_complete = var(False, toggle_class="-show-slash-complete", bindings=True)
    project_path = var(Path())
    working_directory = var("")
    agent_info = var(Content(""))
    _ask: var[Ask | None] = var(None)
    plan: var[list[Plan.Entry]]
    agent_ready: var[bool] = var(False)
    current_mode: var[Mode | None] = var(None)
    modes: var[dict[str, Mode] | None] = var(None)
    status: var[str] = var("")

    app = getters.app(ToadApp)

    def __init__(
        self,
        project_path: Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        complete_callback: Callable[[str], list[str]] | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.ask_queue: list[Ask] = []
        self.complete_callback = complete_callback
        self.project_path = project_path

    @property
    def text(self) -> str:
        return self.prompt_text_area.text

    @text.setter
    def text(self, text: str) -> None:
        self.prompt_text_area.text = text
        self.prompt_text_area.selection = Selection.cursor(
            self.prompt_text_area.get_cursor_line_end_location()
        )

    def watch_current_mode(self, mode: Mode | None) -> None:
        self.set_class(mode is not None, "-has-mode")
        if mode is not None:
            tooltip = Content.from_markup(
                "[b]$description[/]\n\n[dim](click to open mode switcher)",
                description=mode.description,
            )
            self.query_one(ModeInfo).with_tooltip(tooltip).update(mode.name)
        self.watch_modes(self.modes)

    async def watch_project_path(self) -> None:
        """Initial refresh of paths."""
        self.call_later(self.path_search.refresh_paths)

    def ask(self, ask: Ask) -> None:
        """Replace the textarea prompt with a menu of options.

        Args:
            ask: An `Ask` instance which contains a question and responses.
        """
        self.ask_queue.append(ask)
        if self._ask is None:
            self._ask = self.ask_queue.pop(0)

    @on(events.Click, "ModeInfo")
    def on_click(self):
        self.mode_switcher.focus()

    def watch_modes(self, modes: dict[str, Mode] | None) -> None:
        from toad.visuals.columns import Columns

        columns = Columns("auto", "auto", "flex")
        if modes is not None:
            mode_list = sorted(modes.values(), key=lambda mode: mode.name.lower())
            for mode in mode_list:
                columns.add_row(
                    (
                        Content.styled("✔", "$text-success")
                        if self.current_mode and mode.id == self.current_mode.id
                        else ""
                    ),
                    Content.from_markup("[bold]$mode[/]", mode=mode.name),
                    Content.styled(mode.description or "", "dim"),
                )
        else:
            mode_list = []

        self.mode_switcher.set_options(
            [Option(row, id=mode.id) for row, mode in zip(columns, mode_list)]
        )
        if self.current_mode is not None:
            self.mode_switcher.highlighted = self.mode_switcher.get_option_index(
                self.current_mode.id
            )

    def watch_agent_ready(self, ready: bool) -> None:
        self.set_class(not ready, "-not-ready")
        if ready:
            self.query_one(AgentInfo).update(self.agent_info)

    def watch_agent_info(self, agent_info: Content) -> None:
        if self.agent_ready:
            self.query_one(AgentInfo).update(agent_info)
        else:
            self.query_one(AgentInfo).update("Initializing…")

    def watch_multiline(self) -> None:
        self.update_prompt()

    def watch_shell_mode(self) -> None:
        self.update_prompt()

    def watch_working_directory(self, working_directory: str) -> None:
        if not working_directory:
            return
        out_of_bounds = not Path(working_directory).is_relative_to(self.project_path)
        if out_of_bounds and not self.has_class("-working-directory-out-of-bounds"):
            self.post_message(
                messages.Flash(
                    "You have navigated away from the project directory",
                    style="error",
                    duration=5,
                )
            )
        self.set_class(
            out_of_bounds,
            "-working-directory-out-of-bounds",
        )

    def watch__ask(self, ask: Ask | None) -> None:
        self.set_class(ask is not None, "-mode-ask")
        if ask is None:
            self.prompt_text_area.focus()
        else:
            self.question.update(ask)
            self.question.focus()

    def update_prompt(self):
        """Update the prompt according to the current mode."""
        if self.shell_mode:
            self.prompt_label.update(self.PROMPT_SHELL, layout=False)
            self.add_class("-shell-mode")
            self.prompt_text_area.placeholder = Content.from_markup(
                "Enter shell command\t[r]▌esc▐[/r] prompt mode"
            ).expand_tabs(8)
            self.prompt_text_area.highlight_language = "shell"
        else:
            self.prompt_label.update(
                self.PROMPT_MULTILINE if self.multi_line else self.PROMPT_AI,
                layout=False,
            )
            self.remove_class("-shell-mode")

            self.prompt_text_area.placeholder = Content.assemble(
                "What would you like to do?\t".expandtabs(8),
                ("▌!▐", "r"),
                " shell ",
                ("▌/▐", "r"),
                " commands ",
                ("▌@▐", "r"),
                " files",
            )
            self.prompt_text_area.highlight_language = "markdown"

    @property
    def likely_shell(self) -> bool:
        text = self.prompt_text_area.text
        if "\n" in text or " " in text or not text.strip():
            return False

        shell_commands = {
            command.strip()
            for command in self.app.settings.get(
                "shell.allow_commands", expect_type=str
            ).split()
        }
        if text.split(" ", 1)[0] in shell_commands:
            return True
        return False

    @property
    def is_shell_mode(self) -> bool:
        return self.shell_mode or self.likely_shell

    def focus(self, scroll_visible: bool = True) -> Self:
        if self._ask is not None:
            self.question.focus()
        else:
            self.query(HighlightedTextArea).focus()
        return self

    def append(self, text: str) -> None:
        self.query_one(HighlightedTextArea).insert(
            text, maintain_selection_offset=False
        )

    def watch_show_path_search(self, show: bool) -> None:
        self.prompt_text_area.suggestion = ""

    def watch_show_slash_complete(self, show: bool) -> None:
        self.slash_complete.focus()

    def project_directory_updated(self) -> None:
        """Called when there is may be new files"""
        self.path_search.refresh_paths()

    @on(PromptTextArea.RequestShellMode)
    def on_request_shell_mode(self, event: PromptTextArea.RequestShellMode):
        self.shell_mode = True
        self.update_prompt()

    @on(TextArea.Changed)
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        text = event.text_area.text

        self.multi_line = "\n" in text or "```" in text

        if not self.multi_line and self.likely_shell:
            self.shell_mode = True

        self.update_prompt()

    @on(PromptTextArea.CancelShell)
    def on_cancel_shell(self, event: PromptTextArea.CancelShell):
        self.shell_mode = False

    @on(InvokeFileSearch)
    def on_invoke_file_search(self, event: InvokeFileSearch) -> None:
        event.stop()
        if not self.shell_mode:
            self.show_path_search = True
            self.path_search.reset()

    @on(InvokeSlashComplete)
    def on_invoke_slash_complete(self, event: InvokeSlashComplete) -> None:
        event.stop()
        self.show_slash_complete = True

    @on(messages.PromptSuggestion)
    def on_prompt_suggestion(self, event: messages.PromptSuggestion) -> None:
        event.stop()
        self.prompt_text_area.suggestion = event.suggestion

    @on(SlashComplete.Completed)
    def on_slash_complete_completed(self, event: SlashComplete.Completed) -> None:
        self.prompt_text_area.clear()
        self.prompt_text_area.insert(f"{event.command} ")

    @on(messages.Dismiss)
    def on_dismiss(self, event: messages.Dismiss) -> None:
        event.stop()
        if event.widget is self.slash_complete:
            self.show_slash_complete = False
            self.prompt_text_area.suggestion = ""
            self.focus()
        elif event.widget is self.path_search:
            self.show_path_search = False
            self.focus()

    @on(messages.InsertPath)
    def on_insert_path(self, event: messages.InsertPath) -> None:
        event.stop()
        if " " in event.path:
            path = f'"{event.path}"'
        else:
            path = event.path
            if (
                self.prompt_text_area.get_text_range(*self.prompt_text_area.selection)
                != " "
            ):
                path += " "
        self.prompt_text_area.insert(path)

    @on(Question.Answer)
    def on_question_answer(self, event: Question.Answer) -> None:
        """Question has been answered."""
        event.stop()

        def remove_question() -> None:
            """Remove the question and restore the text prompt."""
            if self.ask_queue:
                self._ask = self.ask_queue.pop(0)
            else:
                self._ask = None

        if self._ask is not None and (callback := self._ask.callback) is not None:
            callback(event.answer)

        self.set_timer(0.3, remove_question)

    def suggest(self, suggestion: str) -> None:
        if suggestion.startswith(self.text) and self.text != suggestion:
            self.prompt_text_area.suggestion = suggestion[len(self.text) :]

    def compose(self) -> ComposeResult:
        yield PathSearch(self.project_path).data_bind(root=Prompt.project_path)
        yield SlashComplete().data_bind(slash_commands=Prompt.slash_commands)
        with PromptContainer(id="prompt-container"):
            yield Question()
            with containers.HorizontalGroup(id="text-prompt"):
                yield Label(self.PROMPT_AI, id="prompt")
                yield PromptTextArea().data_bind(
                    multi_line=Prompt.multi_line,
                    shell_mode=Prompt.shell_mode,
                    agent_ready=Prompt.agent_ready,
                    project_path=Prompt.project_path,
                    working_directory=Prompt.working_directory,
                    slash_commands=Prompt.slash_commands,
                )
        with containers.HorizontalGroup(id="info-container"):
            yield AgentInfo()
            yield CondensedPath().data_bind(path=Prompt.working_directory)
            yield StatusLine(markup=False).data_bind(status=Prompt.status)
            yield ModeSwitcher()
            yield ModeInfo("mode")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return True

    def action_dismiss(self) -> None:
        if self.prompt_text_area.suggestion:
            self.prompt_text_area.suggestion = ""
            return
        if self.shell_mode:
            self.shell_mode = False
        elif self.show_slash_complete:
            self.show_slash_complete = False
        else:
            raise SkipAction()
