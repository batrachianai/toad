from __future__ import annotations

from asyncio import Future
import asyncio
from itertools import filterfalse
from operator import attrgetter
import platform
from typing import TYPE_CHECKING, Literal
from pathlib import Path
from time import monotonic

from typing import Callable, Any

from textual import log, on, work
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual import events
from textual.actions import SkipAction
from textual.binding import Binding
from textual.content import Content
from textual.geometry import clamp
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets.markdown import MarkdownBlock, MarkdownFence
from textual.geometry import Offset, Spacing
from textual.reactive import var
from textual.layouts.grid import GridLayout
from textual.layout import WidgetPlacement


from toad import jsonrpc, messages
from toad import paths
from toad.agent_schema import Agent as AgentData
from toad.acp import messages as acp_messages
from toad.app import ToadApp
from toad.acp import protocol as acp_protocol
from toad.acp.agent import Mode
from toad.answer import Answer
from toad.agent import AgentBase, AgentReady, AgentFail
from toad.history import History
from toad.session import SessionStore, SessionEvent
from toad.messages import SessionSelected
from toad.widgets.flash import Flash
from toad.widgets.menu import Menu
from toad.widgets.note import Note
from toad.widgets.prompt import Prompt
from toad.widgets.terminal import Terminal
from toad.widgets.throbber import Throbber
from toad.widgets.user_input import UserInput
from toad.shell import Shell, CurrentWorkingDirectoryChanged, ShellFinished
from toad.slash_command import SlashCommand
from toad.protocol import BlockProtocol, MenuProtocol, ExpandProtocol
from toad.menus import MenuItem

if TYPE_CHECKING:
    from toad.widgets.terminal import Terminal
    from toad.widgets.agent_response import AgentResponse
    from toad.widgets.agent_thought import AgentThought
    from toad.widgets.terminal_tool import TerminalTool


AGENT_FAIL_HELP = """\
## Agent failed to run

**The agent failed to start.**

Check that the agent is installed and up-to-date.

Note that some agents require an ACP adapter to be installed to work with Toad.

- Exit the app, and run `toad` agin
- Select the agent and hit ENTER
- Click the dropdown, select "Install"
- Click the GO button
- Repeat the process to install an ACP adapter (if required)

Some agents may require you to restart your shell (open a new terminal) after installing.

If that fails, ask for help in [Discussions](https://github.com/batrachianai/toad/discussions)!

https://github.com/batrachianai/toad/discussions
"""


class Loading(Static):
    """Tiny widget to show loading indicator."""

    DEFAULT_CLASSES = "block"
    DEFAULT_CSS = """
    Loading {
        height: auto;        
    }
    """


class Cursor(Static):
    """The block 'cursor' -- A vertical line to the left of a block in the conversation that
    is used to navigate the discussion history.
    """

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
    """Holds the agent conversation (input, output, and various controls / information)."""

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
        Binding(
            "enter",
            "select_block",
            "Select",
            tooltip="Select this block",
        ),
        Binding(
            "space",
            "expand_block",
            "Expand",
            key_display="␣",
            tooltip="Expand cursor block",
        ),
        Binding(
            "space",
            "collapse_block",
            "Collapse",
            key_display="␣",
            tooltip="Collapse cursor block",
        ),
        Binding(
            "escape",
            "cancel",
            "Cancel",
            tooltip="Cancel agent's turn",
        ),
        Binding(
            "ctrl+f",
            "focus_terminal",
            "Focus",
            tooltip="Focus the active terminal",
            priority=True,
        ),
        Binding(
            "ctrl+o",
            "mode_switcher",
            "Modes",
            tooltip="Open the mode switcher",
        ),
        Binding(
            "ctrl+c",
            "interrupt",
            "Interrupt",
            tooltip="Interrupt running command",
        ),
    ]

    busy_count = var(0)
    cursor_offset = var(-1, init=False)
    project_path = var(Path("./").expanduser().absolute())
    working_directory: var[str] = var("")
    _blocks: var[list[MarkdownBlock] | None] = var(None)

    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    contents = getters.query_one(Contents)
    window = getters.query_one(Window)
    cursor = getters.query_one(Cursor)
    prompt = getters.query_one(Prompt)
    app = getters.app(ToadApp)

    _shell: var[Shell | None] = var(None)
    shell_history_index: var[int] = var(0, init=False)
    prompt_history_index: var[int] = var(0, init=False)

    agent: var[AgentBase | None] = var(None, bindings=True)
    agent_info: var[Content] = var(Content())
    agent_ready: var[bool] = var(False)
    modes: var[dict[str, Mode]] = var({}, bindings=True)
    current_mode: var[Mode | None] = var(None)
    turn: var[Literal["agent", "client"] | None] = var(None, bindings=True)
    status: var[str] = var("")
    column: var[bool] = var(False, toggle_class="-column")

    def __init__(
        self,
        project_path: Path,
        agent: AgentData | None = None,
        agents: list[AgentData] | None = None,
    ) -> None:
        super().__init__()

        project_path = project_path.resolve().absolute()

        self.set_reactive(Conversation.project_path, project_path)
        self.set_reactive(Conversation.working_directory, str(project_path))
        self.agent_slash_commands: list[SlashCommand] = []
        self.terminals: dict[str, TerminalTool] = {}
        self._loading: Loading | None = None
        self._agent_response: AgentResponse | None = None
        self._agent_thought: AgentThought | None = None
        self._last_escape_time: float = monotonic()
        self._session_summary: str | None = None
        self._session_summary_used: bool = False
        # Normalize agents data into a list
        if agents is not None and agents:
            self._agents_data: list[AgentData] = list(agents)
        elif agent is not None:
            self._agents_data = [agent]
        else:
            self._agents_data = []
        self._agent_data: AgentData | None = (
            self._agents_data[0] if self._agents_data else None
        )
        self._agent_fail = False
        self._mouse_down_offset: Offset | None = None

        self._focusable_terminals: list[Terminal] = []

        self.project_data_path = paths.get_project_data(project_path)
        self.shell_history = History(self.project_data_path / "shell_history.jsonl")
        self.prompt_history = History(self.project_data_path / "prompt_history.jsonl")
        self.session_store = SessionStore(self.project_data_path)

        self.session_start_time: float | None = None

    @property
    def agent_title(self) -> str | None:
        if not self._agents_data:
            return None
        if len(self._agents_data) == 1:
            return self._agents_data[0]["name"]
        names = ", ".join(agent["name"] for agent in self._agents_data)
        return f"Multi: {names}"

    def validate_shell_history_index(self, index: int) -> int:
        return clamp(index, -self.shell_history.size, 0)

    def validate_prompt_history_index(self, index: int) -> int:
        return clamp(index, -self.shell_history.size, 0)

    def shell_complete(self, prefix: str) -> list[str]:
        return self.shell_history.complete(prefix)

    def insert_path_into_prompt(self, path: Path) -> None:
        try:
            insert_path_text = str(path.relative_to(self.project_path))
        except Exception:
            self.app.bell()
            return

        insert_text = (
            f'@"{insert_path_text}"'
            if " " in insert_path_text
            else f"@{insert_path_text}"
        )
        self.prompt.prompt_text_area.insert(insert_text)
        self.prompt.prompt_text_area.insert(" ")

    async def watch_shell_history_index(self, previous_index: int, index: int) -> None:
        if previous_index == 0:
            self.shell_history.current = self.prompt.text
        try:
            history_entry = await self.shell_history.get_entry(index)
        except IndexError:
            pass
        else:
            self.prompt.text = history_entry["input"]
            self.prompt.shell_mode = True

    async def watch_prompt_history_index(self, previous_index: int, index: int) -> None:
        if previous_index == 0:
            self.prompt_history.current = self.prompt.text
        try:
            history_entry = await self.prompt_history.get_entry(index)
        except IndexError:
            pass
        else:
            self.prompt.text = history_entry["input"]

    @on(events.Key)
    async def on_key(self, event: events.Key):
        if (
            event.character is not None
            and event.is_printable
            and event.character.isalnum()
            and self.window.has_focus
        ):
            self.prompt.focus()
            self.prompt.prompt_text_area.post_message(event)

    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        with Window():
            with ContentsGrid():
                with containers.VerticalGroup(id="cursor-container"):
                    yield Cursor()
                yield Contents(id="contents")
        yield Flash()
        yield Prompt(
            self.project_path, complete_callback=self.shell_complete
        ).data_bind(
            project_path=Conversation.project_path,
            working_directory=Conversation.working_directory,
            agent_info=Conversation.agent_info,
            agent_ready=Conversation.agent_ready,
            current_mode=Conversation.current_mode,
            modes=Conversation.modes,
            status=Conversation.status,
        )

    @property
    def _terminal(self) -> Terminal | None:
        """Return the last focusable terminal, if there is one.

        Returns:
            A focusable (non finalized) terminal.
        """
        # Terminals should be removed in response to the Terminal.FInalized message
        # This is a bit of a sanity check
        self._focusable_terminals[:] = list(
            filterfalse(attrgetter("is_finalized"), self._focusable_terminals)
        )
        if self._focusable_terminals:
            return self._focusable_terminals[-1]
        return None

    def add_focusable_terminal(self, terminal: Terminal) -> None:
        """Add a focusable terminal.

        Args:
            terminal: Terminal instance.
        """
        if not terminal.is_finalized:
            self._focusable_terminals.append(terminal)

    @on(Terminal.Finalized)
    def on_terminal_finalized(self, event: Terminal.Finalized) -> None:
        """Terminal was finalized, so we can remove it from the list."""
        try:
            self._focusable_terminals.remove(event.terminal)
        except ValueError:
            pass
        self.prompt.project_directory_updated()

    @on(Terminal.AlternateScreenChanged)
    def on_terminal_alternate_screen_(
        self, event: Terminal.AlternateScreenChanged
    ) -> None:
        """A terminal enabled or disabled alternate screen."""
        if event.enabled:
            event.terminal.focus()
        else:
            self.focus_prompt()

    @on(events.DescendantFocus, "Terminal")
    def on_terminal_focus(self, event: events.DescendantFocus) -> None:
        self.flash("Press [b]escape[/b] [i]twice[/] to exit terminal", style="success")

    @on(events.DescendantBlur, "Terminal")
    def on_terminal_blur(self, event: events.DescendantFocus) -> None:
        self.focus_prompt()

    @on(messages.Flash)
    def on_flash(self, event: messages.Flash) -> None:
        event.stop()
        self.flash(event.content, duration=event.duration, style=event.style)

    def flash(
        self,
        content: str | Content,
        *,
        duration: float | None = None,
        style: Literal["default", "warning", "error", "success"] = "default",
    ) -> None:
        """Flash a single-line message to the user.

        Args:
            content: Content to flash.
            style: A semantic style.
            duration: Duration in seconds of the flash, or `None` to use default in settings.
        """
        self.query_one(Flash).flash(content, duration=duration, style=style)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "focus_terminal":
            return None if self._terminal is None else True
        if action == "mode_switcher":
            return bool(self.modes)
        if action == "cancel":
            return True if (self.agent and self.turn == "agent") else None
        if action in {"expand_block", "collapse_block"}:
            if (cursor_block := self.cursor_block) is None:
                return False
            elif isinstance(cursor_block, ExpandProtocol):
                if action == "expand_block":
                    return False if cursor_block.is_block_expanded() else True
                else:
                    return True if cursor_block.is_block_expanded() else False
            return None if action == "expand_block" else False

        return True

    async def action_focus_terminal(self) -> None:
        if self._terminal is not None:
            self._terminal.focus()
        else:
            self.flash("Nothing to focus...", style="error")

    async def action_expand_block(self) -> None:
        if (cursor_block := self.cursor_block) is not None:
            if isinstance(cursor_block, ExpandProtocol):
                cursor_block.expand_block()
                self.refresh_bindings()
                self.call_after_refresh(self.cursor.follow, cursor_block)

    async def action_collapse_block(self) -> None:
        if (cursor_block := self.cursor_block) is not None:
            if isinstance(cursor_block, ExpandProtocol):
                cursor_block.collapse_block()
                self.refresh_bindings()
                self.call_after_refresh(self.cursor.follow, cursor_block)

    async def post_agent_response(self, fragment: str = "") -> AgentResponse:
        """Get or create an agent response widget."""
        from toad.widgets.agent_response import AgentResponse

        if self._agent_response is None:
            self._agent_response = agent_response = AgentResponse(fragment)
            await self.post(agent_response)
        else:
            await self._agent_response.append_fragment(fragment)
        return self._agent_response

    async def post_agent_thought(self, thought_fragment: str) -> AgentThought:
        """Get or create an agent thought widget."""
        from toad.widgets.agent_thought import AgentThought

        if self._agent_thought is None:
            self._agent_thought = AgentThought(thought_fragment)
            await self.post(self._agent_thought)
        else:
            await self._agent_thought.append_fragment(thought_fragment)
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

    @on(AgentReady)
    async def on_agent_ready(self) -> None:
        if self.session_start_time is None:
            self.session_start_time = monotonic()
            if self.agent is not None:
                content = Content.assemble(self.agent.get_info(), " connected")
                self.flash(content, style="success")
            if self._agents_data:
                for agent_data in self._agents_data:
                    self.app.capture_event(
                        "agent-session-begin",
                        agent=agent_data["identity"],
                    )
            # Start a new stored session the first time the agent becomes ready.
            agent_identities = [agent_data["identity"] for agent_data in self._agents_data]
            self.session_store.start_new_session(self.project_path, agent_identities)

        self.agent_ready = True

    async def on_unmount(self) -> None:
        if self.agent is not None:
            await self.agent.stop()
        if self._agents_data and self.session_start_time is not None:
            session_time = monotonic() - self.session_start_time
            for agent_data in self._agents_data:
                await self.app.capture_event(
                    "agent-session-end",
                    agent=agent_data["identity"],
                    duration=session_time,
                    agent_session_fail=self._agent_fail,
                ).wait()
        # Finalize stored session metadata.
        if self._agent_fail:
            self.session_store.mark_fail()
        self.session_store.end_current_session()

    @on(AgentFail)
    async def on_agent_fail(self, message: AgentFail) -> None:
        self.agent_ready = True
        self._agent_fail = True
        self.notify(message.message, title="Agent failure", severity="error", timeout=5)

        if self._agents_data:
            for agent_data in self._agents_data:
                self.app.capture_event(
                    "agent-session-error",
                    agent=agent_data["identity"],
                    message=message.message,
                    details=message.details,
                )

        if message.message:
            error = Content.assemble(
                Content.from_markup(message.message).stylize("$text-error"),
                " - ",
                Content.from_markup(message.details.strip()).stylize("dim"),
            )
        else:
            error = Content.from_markup(message.details.strip()).stylize("$text-error")
        await self.post(Note(error, classes="-error"))

        from toad.widgets.markdown_note import MarkdownNote

        await self.post(MarkdownNote(AGENT_FAIL_HELP))

    @on(messages.WorkStarted)
    def on_work_started(self) -> None:
        self.busy_count += 1

    @on(messages.WorkFinished)
    def on_work_finished(self) -> None:
        self.busy_count -= 1

    @work
    @on(messages.ChangeMode)
    async def on_change_mode(self, event: messages.ChangeMode) -> None:
        if (agent := self.agent) is None:
            return
        if event.mode_id is None:
            self.current_mode = None
        else:
            if (error := await agent.set_mode(event.mode_id)) is not None:
                self.notify(error, title="Set Mode", severity="error")
            elif (new_mode := self.modes.get(event.mode_id)) is not None:
                self.current_mode = new_mode
                self.flash(
                    Content.from_markup("Mode changed to [b]$mode", mode=new_mode.name),
                    style="success",
                )

    @on(acp_messages.ModeUpdate)
    def on_mode_update(self, event: acp_messages.ModeUpdate) -> None:
        if (modes := self.modes) is not None:
            if (mode := modes.get(event.current_mode)) is not None:
                self.current_mode = mode

    @on(messages.UserInputSubmitted)
    async def on_user_input_submitted(self, event: messages.UserInputSubmitted) -> None:
        if not event.body.strip():
            return
        if event.shell:
            await self.shell_history.append(event.body)
            self.shell_history_index = 0
            # Record shell command in the current session.
            self.session_store.append_event(
                SessionEvent(
                    role="():
            await self.prompt_history.append(event.body)
            self.prompt_history_index = 0
            if text.startswith("/") and await self.slash_command(text):
                # Toad has processed the slash command.
                return
            await self.post(UserInput(text))
            # Record user prompt in the current session.
            self.session_store.append_event(
                SessionEvent(
                    role="user",
                    type="message",
                    text=text,
                    agent_identity=None,
                )
            )
            self._loading = await self.post(Loading("Please wait..."), loading=True)
            await asyncio.sleep(0)
            self.send_prompt_to_agent(text)

    @work
    async def send_prompt_to_agent(self, prompt: str) -> None:
        if self.agent is not None:
            stop_reason: str | None = None
            self.busy_count += 1
            try:
                self.turn = "agent"
                # If we have a stored session summary that hasn't been used yet,
                # prepend it to the user's prompt and mark it as used.
                if self._session_summary and not self._session_summary_used:
                    combined_prompt = (
                        "Here is a summary of the previous conversation context:\n\n"
                        f"{self._session_summary}\n\n"
                        "Use this as background context, then answer the user's request.\n\n"
                        f"User: {prompt}"
                    )
                    self._session_summary_used = True
                    stop_reason = await self.agent.send_prompt(combined_prompt)
                else:
                    stop_reason = await self.agent.send_prompt(prompt)
            except jsonrpc.APIError:
                self.turn = "client"
            finally:
                self.busy_count -= 1
            self.call_later(self.agent_turn_over, stop_reason)

    async def agent_turn_over(self, stop_reason: str | None) -> None:
        """Called when the agent's turn is over.

        Args:
            stop_reason: The stop reason returned from the Agent, or `None`.
        """
        if self._agent_thought is not None and self._agent_thought.loading:
            await self._agent_thought.remove()

        self.turn = "client"
        if self._agent_thought is not None and self._agent_thought.loading:
            await self._agent_thought.remove()
        if self._loading is not None:
            await self._loading.remove()
        self._agent_response = None
        self._agent_thought = None
        self.post_message(messages.ProjectDirectoryUpdated())
        self.prompt.project_directory_updated()
        if self.app.settings.get("notifications.turn_over", bool):
            self.app.system_notify(
                f"{self.agent_title} has finished working",
                title="Waiting for input",
                sound="turn-over",
            )

    @on(Menu.OptionSelected)
    async def on_menu_option_selected(self, event: Menu.OptionSelected) -> None:
        event.stop()
        event.menu.display = False
        if event.action is not None:
            await self.run_action(event.action, {"block": event.owner})
        if (cursor_block := self.get_cursor_block()) is not None:
            self.call_after_refresh(self.cursor.follow, cursor_block)
        self.call_after_refresh(event.menu.remove)

    @on(Menu.Dismissed)
    async def on_menu_dismissed(self, event: Menu.Dismissed) -> None:
        event.stop()
        if event.menu.has_focus:
            self.window.focus(scroll_visible=False)
        await event.menu.remove()

    @on(CurrentWorkingDirectoryChanged)
    def on_current_working_directory_changed(
        self, event: CurrentWorkingDirectoryChanged
    ) -> None:
        if self._terminal is not None:
            self._terminal.finalize()
        self.working_directory = str(Path(event.path).resolve().absolute())

    @on(ShellFinished)
    def on_shell_finished(self) -> None:
        if self._terminal is not None:
            self._terminal.finalize()

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    @on(acp_messages.UpdateStatusLine)
    async def on_update_status_line(self, message: acp_messages.UpdateStatusLine):
        self.status = message.status_line

    def _agent_name_for_identity(self, identity: str) -> str:
        for agent_data in self._agents_data:
            if agent_data["identity"] == identity:
                return agent_data.get("short_name") or agent_data["name"]
        return identity

    @on(acp_messages.Update)
    async def on_acp_agent_message(self, message: acp_messages.Update):
        message.stop()
        self._agent_thought = None
        text = message.text
        agent_identity = message.agent_identity or ""
        if agent_identity and len(self._agents_data) > 1:
            name = self._agent_name_for_identity(agent_identity)
            text = f"[{name}] {text}"
        await self.post_agent_response(text)
        # Record agent message in the current session.
        self.session_store.append_event(
            SessionEvent(
                role="agent",
                type="message",
                text=message.text,
                agent_identity=agent_identity or None,
            )
        )

    @on(acp_messages.Thinking)
    async def on_acp_agent_thinking(self, message: acp_messages.Thinking):
        message.stop()
        text = message.text
        if message.agent_identity and len(self._agents_data) > 1:
            name = self._agent_name_for_identity(message.agent_identity)
            text = f"[{name}] {text}"
        await self.post_agent_thought(text)

    @on(acp_messages.RequestPermission)
    async def on_acp_request_permission(self, message: acp_messages.RequestPermission):
        message.stop()
        options = [
            Answer(option["name"], option["optionId"], option["kind"])
            for option in message.options
        ]
        self.request_permissions(
            message.result_future,
            options,
            message.tool_call,
        )
        self._agent_response = None
        self._agent_thought = None

    @on(acp_messages.Plan)
    async def on_acp_plan(self, message: acp_messages.Plan):
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

    def get_terminal(self, terminal_id: str) -> TerminalTool | None:
        """Get a terminal from its id.

        Args:
            terminal_id: ID of the terminal.

        Returns:
            Terminal instance, or `None` if no terminal was found.
        """
        from toad.widgets.terminal_tool import TerminalTool

        try:
            terminal = self.contents.query_one(f"#{terminal_id}", TerminalTool)
        except NoMatches:
            return None
        if terminal.released:
            return None
        return terminal

    async def action_interrupt(self) -> None:
        if self._terminal is not None:
            await self.shell.interrupt()
            self._shell = None
            self.flash("Command interrupted", style="success")
        else:
            raise SkipAction()

    @work
    @on(acp_messages.CreateTerminal)
    async def on_acp_create_terminal(self, message: acp_messages.CreateTerminal):
        from toad.widgets.terminal_tool import TerminalTool, Command

        command = Command(
            message.command,
            message.args or [],
            message.env or {},
            message.cwd or str(self.project_path),
        )
        width = self.window.size.width - 5 - self.window.styles.scrollbar_size_vertical
        height = self.window.scrollable_content_region.height - 2

        terminal = TerminalTool(
            command,
            output_byte_limit=message.output_byte_limit,
            id=message.terminal_id,
            minimum_terminal_width=width,
        )
        self.terminals[message.terminal_id] = terminal
        terminal.display = False

        try:
            await terminal.start(width, height)
        except Exception as error:
            log(str(error))
            message.result_future.set_result(False)
            return

        try:
            await self.post(terminal)
        except Exception:
            message.result_future.set_result(False)
        else:
            # Treat ACP terminals as focusable so ctrl+f can jump to them.
            self.add_focusable_terminal(terminal)
            message.result_future.set_result(True)

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
            message.result_future.set_result(terminal.tool_state)

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
            return_code, signal = await terminal.wait_for_exit()
            message.result_future.set_result((return_code or 0, signal))

    def set_mode(self, mode_id: str) -> bool:
        """Set the mode give its id (if it exists).

        Args:
            mode_id: Id of mode.

        Returns:
            `True` if the mode was changed, `False` if it didn't exist.
        """
        if (mode := self.modes.get(mode_id)) is not None:
            self.current_mode = mode
            return True
        self.notify(
            f"Node mode called '{mode_id}'",
            title="Error setting mode",
            severity="error",
        )
        return False

    @on(SessionSelected)
    async def on_session_selected(self, message: SessionSelected) -> None:
        """Load a saved session transcript into the current conversation."""
        message.stop()
        events = self.session_store.load_events(message.session_id)
        if not events:
            self.flash("No transcript available for this session", style="warning")
            return

        # Resume this session for future events.
        self.session_store.resume_session(message.session_id)
        self._session_summary = None
        self._session_summary_used = False

        # Clear current contents.
        for child in list(self.contents.children):
            await child.remove()
        self.cursor_offset = -1
        self.cursor.display = False

        from toad.widgets.user_input import UserInput as UserInputWidget
        from toad.widgets.agent_response import AgentResponse as AgentResponseWidget
        from toad.widgets.shell_result import ShellResult
        from textual.widgets import Static

        # Rebuild a simple transcript: user prompts, agent messages, and shell activity.
        # Build a simple textual transcript and keep it for summarization.
        transcript_lines: list[str] = []
        for event_data in events:
            role = event_data.get("role")
            text = event_data.get("text") or ""
            event_type = event_data.get("type")
            if not text:
                continue
            if role == "user" and event_type == "message":
                await self.post(UserInputWidget(text), anchor=False)
                transcript_lines.append(f"User: {text}")
            elif role == "agent" and event_type == "message":
                await self.post(AgentResponseWidget(text), anchor=False)
                transcript_lines.append(f"Agent: {text}")
            elif role == "shell" and event_type == "shell_command":
                await self.post(ShellResult(text), anchor=False)
                transcript_lines.append(f"Shell command: {text}")
            elif role == "shell" and event_type == "shell_output":
                # Render output as a simple Static block.
                await self.post(Static(text, classes="shell-output"), anchor=False)
                transcript_lines.append(f"Shell output: {text}")

        # If the transcript is long, generate a summary that will be injected
        # into the next prompt sent to the agent.
        transcript = "\n".join(transcript_lines)
        if len(transcript) > 2000 and self.agent is not None:
            # Ask the agent itself to summarize the transcript.
            summary_prompt = (
                "Summarize the following previous session into a concise summary "
                "that captures important goals, decisions, code changes, and open questions. "
                "Use plain text, no markdown, and keep it under 300 words.\n\n"
                f"{transcript}"
            )
            try:
                self._session_summary = await self.agent.send_prompt(summary_prompt)
                self._session_summary_used = False
                self.flash(
                    "Session is long; a summary will be used as context for your next prompt.",
                    style="information",
                )
            except Exception:
                self._session_summary = None
                self._session_summary_used = False

        self.window.scroll_end()
        self.flash("Session loaded. New messages will be appended here.", style="success")

    async def slash_command(self, text: str) -> bool:
        """Give Toad the opertunity to process slash commands.

        Args:
            text: The prompt, including the slash in the first position.

        Returns:
            `True` if Toad has processed the slash command, `False` if it should
                be forwarded to the agent.
        """
        command, _, parameters = text[1:].partition(" ")
        if command == "about-toad":
            from toad import about
            from toad.widgets.markdown_note import MarkdownNote

            app = self.app
            about_md = about.render(app)
            await self.post(MarkdownNote(about_md, classes="about"))
            self.app.copy_to_clipboard(about_md)
            self.notify(
                "A copy of /about-toad has been placed in your clipboard",
                title="About",
            )
            return True
        if command == "rename-session":
            title = parameters.strip()
            if not title:
                self.flash("Usage: /rename-session &lt;new title&gt;", style="warning")
                return True
            session_id = self.session_store.current_session_id
            if session_id is None:
                # Fall back to latest session for this project.
                sessions = self.session_store.list_sessions()
                session_id = sessions[0]["session_id"] if sessions else None
            if session_id is None:
                self.flash("No session to rename.", style="warning")
                return True
            self.session_store.rename_session(session_id, title)
            # Refresh sessions panel if present.
            from toad.widgets.sessions import Sessions

            for sessions_widget in self.screen.query(Sessions):
                await sessions_widget.reload()
            self.flash(f"Session renamed to '{title}'", style="success")
            return True
        return False
