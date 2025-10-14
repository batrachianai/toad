from __future__ import annotations

from asyncio import Future
from functools import cached_property
from operator import attrgetter
from typing import TYPE_CHECKING
from pathlib import Path

from typing import Callable, Any

from textual import log, on, work
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual import events
from textual.binding import Binding
from textual.content import Content
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets.markdown import MarkdownBlock, MarkdownFence
from textual.geometry import Offset, Spacing
from textual.reactive import var, Initialize
from textual.layouts.grid import GridLayout
from textual.layout import WidgetPlacement


import llm

from toad import jsonrpc, messages
from toad.acp import messages as acp_messages
from toad.app import ToadApp
from toad.acp import protocol as acp_protocol
from toad.answer import Answer
from toad.agent import AgentBase
from toad.widgets.menu import Menu
from toad.widgets.note import Note
from toad.widgets.prompt import Prompt
from toad.widgets.throbber import Throbber
from toad.widgets.user_input import UserInput
from toad.widgets.explain import Explain
from toad.shell import Shell, CurrentWorkingDirectoryChanged
from toad.slash_command import SlashCommand
from toad.protocol import BlockProtocol, MenuProtocol
from toad.menus import CONVERSATION_MENUS, MenuItem

if TYPE_CHECKING:
    from toad.widgets.ansi_log import ANSILog
    from toad.widgets.agent_response import AgentResponse
    from toad.widgets.agent_thought import AgentThought
    from toad.widgets.terminal import Terminal


class Cursor(Static):
    follow_widget: var[Widget | None] = var(None)
    blink = var(True, toggle_class="-blink")

    def on_mount(self) -> None:
        self.display = False
        self.blink_timer = self.set_interval(0.5, self._update_blink, pause=True)
        self.set_interval(0.4, self._update_follow)

    def _update_blink(self) -> None:
        if self.query_ancestor(Window).has_focus and self.screen.is_active:
            self.blink = not self.blink
        else:
            self.blink = True

    def watch_follow_widget(self, widget: Widget | None) -> None:
        self.display = widget is not None

    def _update_follow(self) -> None:
        if self.follow_widget and self.follow_widget.is_attached:
            self.styles.height = max(1, self.follow_widget.outer_size.height)
            follow_y = (
                self.follow_widget.virtual_region.y
                + self.follow_widget.parent.virtual_region.y
            )
            self.offset = Offset(0, follow_y)

    def follow(self, widget: Widget | None) -> None:
        self.follow_widget = widget
        self.blink = False
        if widget is None:
            self.display = False
            self.blink_timer.reset()
            self.blink_timer.pause()
        else:
            self.display = True
            self.blink_timer.reset()
            self.blink_timer.resume()
            self._update_follow()


class Contents(containers.VerticalGroup, can_focus=False):
    def process_layout(
        self, placements: list[WidgetPlacement]
    ) -> list[WidgetPlacement]:
        if placements:
            last_placement = placements[-1]
            top, right, bottom, left = last_placement.margin
            placements[-1] = last_placement._replace(
                margin=Spacing(top, right, 0, left)
            )
        return placements


class ContentsGrid(containers.Grid):
    def pre_layout(self, layout) -> None:
        assert isinstance(layout, GridLayout)
        layout.stretch_height = True


class Window(containers.VerticalScroll):
    BINDING_GROUP_TITLE = "View"
    BINDINGS = [Binding("end", "screen.focus_prompt", "Prompt")]


class Conversation(containers.Vertical):
    BINDING_GROUP_TITLE = "Conversation"
    CURSOR_BINDING_GROUP = Binding.Group(description="Cursor")
    BINDINGS = [
        Binding(
            "alt+up",
            "cursor_up",
            "Block cursor up",
            priority=True,
            group=CURSOR_BINDING_GROUP,
        ),
        Binding(
            "alt+down",
            "cursor_down",
            "Block cursor down",
            group=CURSOR_BINDING_GROUP,
        ),
        Binding("enter", "select_block", "Select"),
        Binding("escape", "dismiss", "Dismiss", show=False),
        Binding("f2,ctrl+comma", "settings", "Settings"),
    ]

    busy_count = var(0)
    cursor_offset = var(-1, init=False)
    project_path = var(Path("./").expanduser().absolute())
    _blocks: var[list[MarkdownBlock] | None] = var(None)

    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    contents = getters.query_one(Contents)
    window = getters.query_one(Window)
    cursor = getters.query_one(Cursor)
    prompt = getters.query_one(Prompt)
    app = getters.app(ToadApp)

    def create_shell(self) -> Shell:
        return Shell(self)

    shell: var[Shell] = var(Initialize(create_shell))

    agent: var[AgentBase | None] = var(None)
    agent_info: var[Content] = var(Content())
    _agent_response: var[AgentResponse | None] = var(None)
    _agent_thought: var[AgentThought | None] = var(None)

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self.set_reactive(Conversation.project_path, project_path)
        self.agent_slash_commands: list[SlashCommand] = []
        self.slash_command_hints: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        with Window():
            with ContentsGrid():
                with containers.VerticalGroup(id="cursor-container"):
                    yield Cursor()
                yield Contents(id="contents")
        yield Prompt().data_bind(
            project_path=Conversation.project_path, agent_info=Conversation.agent_info
        )

    @cached_property
    def conversation(self) -> llm.Conversation:
        return llm.get_model(self.app.settings.get("llm.model", str)).conversation()

    async def get_agent_response(self) -> AgentResponse:
        """Get or create an agent response widget."""
        from toad.widgets.agent_response import AgentResponse

        if self._agent_response is None:
            self._agent_response = agent_response = AgentResponse(
                self.conversation, None
            )
            await self.post(self._agent_response)
            return agent_response

        return self._agent_response

    async def get_agent_thought(self) -> AgentThought:
        """Get or create an agent thought widget."""
        from toad.widgets.agent_thought import AgentThought

        if self.contents.children and not isinstance(
            self.contents.children[-1], AgentThought
        ):
            if self._agent_thought is not None:
                self._agent_thought.loading = False
            self._agent_thought = None

        if self._agent_thought is None:
            agent_thought = self._agent_thought = AgentThought("")
            await self.post(self._agent_thought, loading=True)
            return agent_thought
        return self._agent_thought

    @property
    def cursor_block(self) -> Widget | None:
        """The block next to the cursor, or `None` if no block cursor."""
        if self.cursor_offset == -1 or not self.contents.displayed_children:
            return None
        try:
            block_widget = self.contents.displayed_children[self.cursor_offset]
        except IndexError:
            return None
        return block_widget

    @property
    def cursor_block_child(self) -> Widget | None:
        if (cursor_block := self.cursor_block) is not None:
            if isinstance(cursor_block, BlockProtocol):
                return cursor_block.get_cursor_block()
        return cursor_block

    def get_cursor_block[BlockType](
        self, block_type: type[BlockType] = Widget
    ) -> BlockType | None:
        """Get the cursor block if it matches a type.

        Args:
            block_type: The expected type.

        Returns:
            The widget next to the cursor, or `None` if the types don't match.
        """
        cursor_block = self.cursor_block_child
        if isinstance(cursor_block, block_type):
            return cursor_block
        return None

    @on(messages.WorkStarted)
    def on_work_started(self) -> None:
        self.busy_count += 1

    @on(messages.WorkFinished)
    def on_work_finished(self) -> None:
        self.busy_count -= 1

    @on(messages.UserInputSubmitted)
    async def on_user_input_submitted(self, event: messages.UserInputSubmitted) -> None:
        if event.shell:
            await self.post_shell(event.body)
            self.prompt.shell_mode = False
        elif text := event.body.strip():
            if text.startswith("/"):
                await self.slash_command(text)
            else:
                await self.post(UserInput(text))
                await self.get_agent_thought()
                self.send_prompt_to_agent(text)

    @work
    async def send_prompt_to_agent(self, prompt: str) -> None:
        if self.agent is not None:
            stop_reason: str | None = None
            self.busy_count += 1
            try:
                stop_reason = await self.agent.send_prompt(prompt)
            except jsonrpc.APIError as error:
                self.notify(error.message, title="Send prompt", severity="error")
            finally:
                self.busy_count -= 1
            await self.agent_turn_over(stop_reason)

    async def agent_turn_over(self, stop_reason: str | None) -> None:
        """Called when the agent's turn is over.

        Args:
            stop_reason: The stop reason returned from the Agent, or `None`.
        """
        if self._agent_thought is not None and self._agent_thought.loading:
            await self._agent_thought.remove()

        self._agent_response = None
        self._agent_thought = None

    @on(Menu.OptionSelected)
    async def on_menu_option_selected(self, event: Menu.OptionSelected) -> None:
        await event.menu.remove()
        self.window.focus(scroll_visible=False)
        if event.action is not None:
            self.call_after_refresh(
                self.run_action, event.action, {"block": event.owner}
            )

    @on(Menu.Dismissed)
    async def on_menu_dismissed(self, event: Menu.Dismissed) -> None:
        event.stop()
        self.window.focus(scroll_visible=False)
        await event.menu.remove()

    @on(CurrentWorkingDirectoryChanged)
    def on_current_working_directory_changed(
        self, event: CurrentWorkingDirectoryChanged
    ) -> None:
        self.prompt.current_directory.path = event.path

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    @on(acp_messages.Update)
    async def on_acp_agent_message(self, message: acp_messages.Update):
        message.stop()
        if self._agent_thought and self._agent_thought.loading:
            await self._agent_thought.remove()
        agent_response = await self.get_agent_response()
        await agent_response.append_fragment(message.text)

    @on(acp_messages.Thinking)
    async def on_acp_agent_thinking(self, message: acp_messages.Thinking):
        message.stop()
        agent_thought = await self.get_agent_thought()
        await agent_thought.append_fragment(message.text)

    @on(acp_messages.RequestPermission)
    async def on_acp_request_permission(self, message: acp_messages.RequestPermission):
        message.stop()
        options = [
            Answer(
                option["name"],
                option["optionId"],
            )
            for option in message.options
        ]
        self.request_permissions(
            message.result_future,
            options,
            message.tool_call,
        )

    @on(acp_messages.Plan)
    async def on_acp_plan(self, message: acp_messages.Plan):
        message.stop()
        from toad.widgets.plan import Plan

        entries = [
            Plan.Entry(
                Content(entry["content"]),
                entry.get("priority", "medium"),
                entry.get("status", "pending"),
            )
            for entry in message.entries
        ]

        if self.contents.children and isinstance(
            (current_plan := self.contents.children[-1]), Plan
        ):
            current_plan.entries = entries
        else:
            await self.post(Plan(entries))

    @on(acp_messages.ToolCallUpdate)
    @on(acp_messages.ToolCall)
    async def on_acp_tool_call_update(
        self, message: acp_messages.ToolCall | acp_messages.ToolCallUpdate
    ):
        from toad.widgets.tool_call import ToolCall

        tool_call = message.tool_call

        if tool_call.get("status", None) in (None, "completed"):
            self._agent_thought = None
            self._agent_response = None

        tool_id = message.tool_id
        try:
            existing_tool_call: ToolCall | None = self.contents.get_child_by_id(
                tool_id, ToolCall
            )
        except NoMatches:
            await self.post(ToolCall(tool_call, id=message.tool_id))
        else:
            existing_tool_call.tool_call = tool_call

    @on(acp_messages.AvailableCommandsUpdate)
    async def on_acp_available_commands_update(
        self, message: acp_messages.AvailableCommandsUpdate
    ):
        slash_commands: list[SlashCommand] = []
        for available_command in message.commands:
            input = available_command.get("input", {}) or {}
            slash_command = SlashCommand(
                f"/{available_command['name']}",
                available_command["description"],
                hint=input.get("hint"),
            )
            slash_commands.append(slash_command)
        self.agent_slash_commands = slash_commands
        self.update_slash_commands()

    def get_terminal(self, terminal_id: str) -> Terminal | None:
        """Get a terminal from its id.

        Args:
            terminal_id: ID of the terminal.

        Returns:
            Terminal instance, or `None` if no terminal was found.
        """
        from toad.widgets.terminal import Terminal

        try:
            terminal = self.contents.query_one(f"#{terminal_id}", Terminal)
        except NoMatches:
            return None
        if terminal.released:
            return None
        return terminal

    @on(acp_messages.CreateTerminal)
    async def on_acp_create_terminal(self, message: acp_messages.CreateTerminal):
        from toad.widgets.terminal import Terminal, Command

        command = Command(
            message.command,
            message.args or [],
            message.env or {},
            message.cwd or str(self.project_path),
        )
        terminal = Terminal(
            command,
            output_byte_limit=message.output_byte_limit,
            id=message.terminal_id,
        )
        # terminal.display = False
        width, height = self.contents.scrollable_content_region.size
        width -= 4
        terminal.start(width, height)
        await self.post(terminal)

    @on(acp_messages.KillTerminal)
    async def on_acp_kill_terminal(self, message: acp_messages.KillTerminal):
        if (terminal := self.get_terminal(message.terminal_id)) is not None:
            terminal.kill()

    @on(acp_messages.GetTerminalState)
    def on_acp_get_terminal_state(self, message: acp_messages.GetTerminalState):
        if (terminal := self.get_terminal(message.terminal_id)) is None:
            message.result_future.set_exception(
                KeyError(f"No terminal with id {message.terminal_id!r}")
            )
        else:
            message.result_future.set_result(terminal.state)

    @on(acp_messages.ReleaseTerminal)
    def on_acp_terminal_release(self, message: acp_messages.ReleaseTerminal):
        if (terminal := self.get_terminal(message.terminal_id)) is not None:
            terminal.kill()
            terminal.release()

    @work
    @on(acp_messages.WaitForTerminalExit)
    async def on_acp_wait_for_terminal_exit(
        self, message: acp_messages.WaitForTerminalExit
    ):
        if (terminal := self.get_terminal(message.terminal_id)) is None:
            message.result_future.set_exception(
                KeyError(f"No terminal with id {message.terminal_id!r}")
            )
        else:
            print("WAITING for exit")
            return_code, signal = await terminal.wait_for_exit()
            message.result_future.set_result((return_code or 0, signal))

    @work
    async def request_permissions(
        self,
        result_future: Future[Answer],
        options: list[Answer],
        tool_call_update: acp_protocol.ToolCallUpdatePermissionRequest,
    ) -> None:
        kind = tool_call_update.get("kind")

        log(tool_call_update)

        if kind is None:
            from toad.widgets.tool_call import ToolCall

            if (contents := tool_call_update.get("content")) is None:
                return
            title = tool_call_update.get("title")
            for content in contents:
                match content:
                    case {"type": "text", "content": {"text": text}}:
                        await self.post(ToolCall(text))

            def answer_callback(answer: Answer) -> None:
                result_future.set_result(answer)

            self.ask(options, title or "", answer_callback)
            return

        if kind == "edit":
            from toad.screens.permissions import PermissionsScreen

            async def populate(screen: PermissionsScreen) -> None:
                if (contents := tool_call_update.get("content")) is None:
                    return
                for content in contents:
                    match content:
                        case {
                            "type": "diff",
                            "oldText": old_text,
                            "newText": new_text,
                            "path": path,
                        }:
                            await screen.add_diff(path, path, old_text, new_text)

            permissions_screen = PermissionsScreen(options, populate_callback=populate)
            result = await self.app.push_screen_wait(permissions_screen)
            result_future.set_result(result)
        elif kind == "execute":
            title = tool_call_update.get("title", "") or ""

            def answer_callback(answer: Answer) -> None:
                result_future.set_result(answer)

            self.ask(options, title, answer_callback)

    async def post_tool_call(
        self, tool_call_update: acp_protocol.ToolCallUpdate
    ) -> None:
        if (contents := tool_call_update.get("content")) is None:
            return

        for content in contents:
            match content:
                case {
                    "type": "diff",
                    "oldText": old_text,
                    "newText": new_text,
                    "path": path,
                }:
                    await self.post_diff(path, old_text, new_text)

    async def post_diff(self, path: str, before: str | None, after: str) -> None:
        """Post a diff view.

        Args:
            path: Path to the file.
            before: Content of file before edit.
            after: Content of file after edit.
        """
        from toad.widgets.diff_view import DiffView

        diff_view = DiffView(path, path, before or "", after, classes="block")
        diff_view_setting = self.app.settings.get("diff.view", str)
        diff_view.split = diff_view_setting == "split"
        diff_view.auto_split = diff_view_setting == "auto"
        await self.post(diff_view)

    def ask(
        self,
        options: list[Answer],
        question: str = "",
        callback: Callable[[Answer], Any] | None = None,
    ) -> None:
        """Replace the prompt with a dialog to ask a question

        Args:
            question: Question to ask or empty string to omit.
            options: A list of (ANSWER, ANSWER_ID) tuples.
            callback: Optional callable that will be invoked with the result.
        """
        from toad.widgets.question import Ask

        self.prompt.ask = Ask(question, options, callback)

    def _build_slash_commands(self) -> list[SlashCommand]:
        slash_commands = [
            SlashCommand("/about", "About Toad"),
            # SlashCommand("/help", "Open Help"),
            # SlashCommand("/set", "Change a setting"),
        ]
        slash_commands.extend(self.agent_slash_commands)
        slash_commands.sort(key=attrgetter("command"))

        self.slash_command_hints = {
            slash_command.command: slash_command.hint
            for slash_command in slash_commands
            if slash_command.hint
        }

        return slash_commands

    def update_slash_commands(self) -> None:
        """Update slash commands, which may have changed since mounting."""
        self.prompt.slash_commands = self._build_slash_commands()

    async def on_mount(self) -> None:
        self.prompt.focus()
        self.prompt.slash_commands = self._build_slash_commands()
        self.call_after_refresh(self.post_welcome)
        self.app.settings_changed_signal.subscribe(self, self._settings_changed)
        self.call_after_refresh(self.start_shell)

        if self.app.acp_command is not None:

            def start_agent():
                from toad.acp.agent import Agent

                assert self.app.acp_command is not None
                self.agent = Agent(self.project_path, self.app.acp_command)
                self.agent.start(self)

            self.call_after_refresh(start_agent)

    @work
    async def start_shell(self) -> None:
        await self.shell.run()

    def _settings_changed(self, setting_item: tuple[str, str]) -> None:
        key, value = setting_item
        if key == "llm.model":
            self.conversation = llm.get_model(value).conversation()

    @work
    async def post_welcome(self) -> None:
        # from toad.widgets.welcome import Welcome

        # await self.post(Welcome(classes="note", name="welcome"), anchor=False)
        await self.post(
            Note(f"Settings read from [$text-success]'{self.app.settings_path}'"),
            anchor=True,
        )
        await self.post(
            Note(f"project directory is [$text-success]'{self.project_path!s}'"),
            anchor=True,
        )

        # notes_path = Path(__file__).parent / "../../../notes.md"
        # from toad.widgets.markdown_note import MarkdownNote

        # await self.post(
        #     MarkdownNote(notes_path.read_text(), name="read_text", classes="note")
        # )

        # from toad.widgets.agent_response import AgentResponse

        # agent_response = AgentResponse(self.conversation)
        # await self.post(agent_response)
        # agent_response.update(MD)

        # from toad.widgets.question import Ask

        # OPTIONS = [
        #     ("Yes, allow once", "proceed_always"),
        #     ("Yes, allow always", "allow_always"),
        #     ("Modify with external editor", "modify"),
        #     ("No, suggest changes (esc)", "reject"),
        # ]

        # self.prompt.ask = Ask(
        #     "What would you like to do?",
        #     OPTIONS,
        # )

    def watch_agent(self, agent: AgentBase | None) -> None:
        if agent is None:
            self.agent_info = Content.styled("shell")
        else:
            self.agent_info = agent.get_info()

    def on_click(self, event: events.Click) -> None:
        widget = event.widget
        contents = self.contents
        if self.screen.get_selected_text():
            return
        if widget is None or widget.is_maximized:
            return
        if widget in contents.displayed_children:
            self.cursor_offset = contents.displayed_children.index(widget)
            self.refresh_block_cursor()
            return
        for parent in widget.ancestors:
            if not isinstance(parent, Widget):
                break
            if (
                parent is self or parent is contents
            ) and widget in contents.displayed_children:
                self.cursor_offset = contents.displayed_children.index(widget)
                self.refresh_block_cursor()
                break
            if (
                isinstance(parent, BlockProtocol)
                and parent in contents.displayed_children
            ):
                self.cursor_offset = contents.displayed_children.index(parent)
                parent.block_select(widget)
                self.refresh_block_cursor()
                break
            widget = parent
        # self.call_after_refresh(self.refresh_block_cursor)
        # event.stop()

    async def post[WidgetType: Widget](
        self, widget: WidgetType, *, anchor: bool = True, loading: bool = False
    ) -> WidgetType:
        await self.contents.mount(widget)
        widget.loading = loading
        if anchor:
            self.window.anchor()
        return widget

    async def get_ansi_log(self, width: int, display: bool = True) -> ANSILog:
        from toad.widgets.ansi_log import ANSILog

        if self.children and isinstance(self.children[-1], ANSILog):
            ansi_log = self.children[-1]
        else:
            ansi_log = ANSILog(minimum_terminal_width=width)
            ansi_log.display = display
            ansi_log = await self.post(ansi_log)
        return ansi_log

    async def post_shell(self, command: str) -> None:
        from toad.widgets.shell_result import ShellResult

        if command.strip():
            await self.post(ShellResult(command))
        self.call_after_refresh(
            self.shell.send,
            command,
            self.scrollable_content_region.width - 5,
            self.window.scrollable_content_region.height - 2,
        )

    def action_cursor_up(self) -> None:
        if not self.contents.displayed_children or self.cursor_offset == 0:
            # No children
            return
        if self.cursor_offset == -1:
            # Start cursor at end
            self.cursor_offset = len(self.contents.displayed_children) - 1
            cursor_block = self.cursor_block
            if isinstance(cursor_block, BlockProtocol):
                cursor_block.block_cursor_clear()
                cursor_block.block_cursor_up()
        else:
            cursor_block = self.cursor_block
            if isinstance(cursor_block, BlockProtocol):
                if cursor_block.block_cursor_up() is None:
                    self.cursor_offset -= 1
                    cursor_block = self.cursor_block
                    if isinstance(cursor_block, BlockProtocol):
                        cursor_block.block_cursor_clear()
                        cursor_block.block_cursor_up()
            else:
                # Move cursor up
                self.cursor_offset -= 1
                cursor_block = self.cursor_block
                if isinstance(cursor_block, BlockProtocol):
                    cursor_block.block_cursor_clear()
                    cursor_block.block_cursor_up()
        self.refresh_block_cursor()

    def action_cursor_down(self) -> None:
        if not self.contents.displayed_children or self.cursor_offset == -1:
            # No children, or no cursor
            return

        cursor_block = self.cursor_block
        if isinstance(cursor_block, BlockProtocol):
            if cursor_block.block_cursor_down() is None:
                self.cursor_offset += 1
                if self.cursor_offset >= len(self.contents.displayed_children):
                    self.cursor_offset = -1
                    self.refresh_block_cursor()
                    return
                cursor_block = self.cursor_block
                if isinstance(cursor_block, BlockProtocol):
                    cursor_block.block_cursor_clear()
                    cursor_block.block_cursor_down()
        else:
            self.cursor_offset += 1
            if self.cursor_offset >= len(self.contents.displayed_children):
                self.cursor_offset = -1
                self.refresh_block_cursor()
                return
            cursor_block = self.cursor_block
            if isinstance(cursor_block, BlockProtocol):
                cursor_block.block_cursor_clear()
                cursor_block.block_cursor_down()
        self.refresh_block_cursor()

    # def action_dismiss(self) -> None:
    #     self.cursor_offset = -1

    def focus_prompt(self) -> None:
        self.cursor_offset = -1
        self.cursor.display = False
        self.window.scroll_end()
        self.prompt.focus()

    async def action_select_block(self) -> None:
        if (block := self.get_cursor_block(Widget)) is None:
            return

        menu_options = [
            MenuItem("[u]C[/]opy to clipboard", "copy_to_clipboard", "c"),
            MenuItem("Co[u]p[/u]y to prompt", "copy_to_prompt", "p"),
            MenuItem("Open as S[u]V[/]G", "export_to_svg", "v"),
        ]

        if block.allow_maximize:
            menu_options.append(MenuItem("[u]M[/u]aximize", "maximize_block", "m"))

        if isinstance(block, MenuProtocol):
            menu_options.extend(block.get_block_menu())
            menu = Menu(block, menu_options)

        elif isinstance(block, MarkdownBlock):
            if block.name is None:
                self.app.bell()
                return

            menu_options.append(
                MenuItem("Explain this", "explain", "e"),
            )
            menu_options.extend(CONVERSATION_MENUS.get(block.name, []))

            from toad.code_analyze import get_special_name_from_code

            if (
                block.name == "fence"
                and isinstance(block, MarkdownFence)
                and block.source
            ):
                for numeral, name in enumerate(
                    get_special_name_from_code(block.source, block.lexer), 1
                ):
                    menu_options.append(
                        MenuItem(
                            f"Explain '{name}'", f"explain('{name}')", f"{numeral}"
                        )
                    )

            menu = Menu(block, menu_options)
        else:
            # menu_options.extend(block.get_block_menu())
            menu = Menu(block, menu_options)
            # self.notify("This block has no menu", title="Menu", severity="information")
            # self.app.bell()
            # return

        menu.offset = Offset(1, block.region.offset.y)
        await self.mount(menu)
        menu.focus()

    def action_copy_to_clipboard(self) -> None:
        block = self.get_cursor_block()
        if isinstance(block, MenuProtocol):
            text = block.get_block_content("clipboard")
        elif isinstance(block, MarkdownBlock):
            text = block.source
        else:
            return
        if text:
            self.app.copy_to_clipboard(text)
            self.notify("Copied to clipboard")

    def action_copy_to_prompt(self) -> None:
        block = self.get_cursor_block()
        if isinstance(block, MenuProtocol):
            text = block.get_block_content("prompt")
        elif isinstance(block, MarkdownBlock):
            text = block.source
        else:
            return

        if text:
            self.prompt.append(text)
            self.focus_prompt()

    def action_maximize_block(self) -> None:
        if (block := self.get_cursor_block()) is not None:
            self.screen.maximize(block, container=False)
            block.focus()

    def action_export_to_svg(self) -> None:
        block = self.get_cursor_block()
        if block is None:
            return
        import platformdirs
        from textual._compositor import Compositor
        from textual._files import generate_datetime_filename

        width, height = block.outer_size
        compositor = Compositor()
        compositor.reflow(block, block.outer_size)
        render = compositor.render_full_update()

        from rich.console import Console
        import io
        import os.path

        console = Console(
            width=width,
            height=height,
            file=io.StringIO(),
            force_terminal=True,
            color_system="truecolor",
            record=True,
            legacy_windows=False,
            safe_box=False,
        )
        console.print(render)
        path = platformdirs.user_pictures_dir()
        svg_filename = generate_datetime_filename("Toad", ".svg", None)
        svg_path = os.path.expanduser(os.path.join(path, svg_filename))
        console.save_svg(svg_path)
        import webbrowser

        webbrowser.open(f"file:///{svg_path}")

    def action_explain(self, topic: str | None = None) -> None:
        if (block := self.get_cursor_block(MarkdownBlock)) is not None and block.source:
            if topic:
                PROMPT = f"Explain the purpose of '{topic}' in the following code:\n{block.source}"
            else:
                PROMPT = f"Explain the following:\n{block.source}"
            self.screen.query_one(Explain).send_prompt(PROMPT)

    def action_run(self) -> None:
        if (block := self.get_cursor_block(MarkdownBlock)) is not None and block.source:
            assert isinstance(block, MarkdownFence)
            self.execute(block._content.plain, block.lexer)

    @work
    async def action_settings(self) -> None:
        from toad.screens.settings import SettingsScreen

        await self.app.push_screen_wait(SettingsScreen())
        self.app.save_settings()

    @work
    async def execute(self, code: str, language: str) -> None:
        if language == "python":
            command = "python run"
        elif language == "bash":
            command = "sh run"
        else:
            self.notify(
                f"Toad doesn't know how to run '{language}' code yet",
                title="Run",
                severity="error",
            )

        with open("run", mode="wt", encoding="utf-8") as source:
            source.write(code)

        await self.post_shell(command)

    def refresh_block_cursor(self) -> None:
        if (cursor_block := self.cursor_block_child) is not None:
            self.window.focus()
            self.cursor.visible = True
            self.cursor.follow(cursor_block)
            self.call_after_refresh(
                self.window.scroll_to_center, cursor_block, immediate=True
            )
        else:
            self.cursor.visible = False
            self.window.anchor(False)
            self.window.scroll_end(duration=2 / 10)
            self.cursor.follow(None)
            self.prompt.focus()

    async def slash_command(self, text: str) -> None:
        command, _, parameters = text[1:].partition(" ")
        if command == "about":
            from toad import about
            from toad.widgets.markdown_note import MarkdownNote

            await self.post(MarkdownNote(about.render(), classes="about"))
