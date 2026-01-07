from __future__ import annotations

from asyncio import Future
import asyncio
from contextlib import suppress
from itertools import filterfalse
from operator import attrgetter
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
from toad.directory_watcher import DirectoryWatcher, DirectoryChanged
from toad.history import History
from toad.widgets.flash import Flash
from toad.widgets.menu import Menu
from toad.widgets.note import Note
from toad.widgets.prompt import Prompt
from toad.widgets.terminal import Terminal
from toad.widgets.throbber import Throbber
from toad.widgets.user_input import UserInput
from toad.shell import Shell, CurrentWorkingDirectoryChanged
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

HELP_URL = "https://github.com/batrachianai/toad/discussions"

STOP_REASON_MAX_TOKENS = f"""\
## Maximum tokens reached

$AGENT reported that your account is out of tokens.

- You may need to purchase additional tokens, or fund your account.
- If your account has tokens, try running any login or auth process again.

If that fails, ask on {HELP_URL}
"""

STOP_REASON_MAX_TURN_REQUESTS = f"""\
## Maximum model requests reached

$AGENT has exceeded the maximum number of model requests in a single turn.

Need help? Ask on {HELP_URL}
"""

STOP_REASON_REFUSAL = """\
## Agent refusal
 
$AGENT has refused to continue. 

Need help? Ask on {HELP_URL}
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
        self.visible = False
        self.blink_timer = self.set_interval(0.5, self._update_blink, pause=True)

    def _update_blink(self) -> None:
        if self.query_ancestor(Window).has_focus and self.screen.is_active:
            self.blink = not self.blink
        else:
            self.blink = False

    def watch_follow_widget(self, widget: Widget | None) -> None:
        self.visible = widget is not None

    def update_follow(self) -> None:
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
            self.visible = False
            self.blink_timer.reset()
            self.blink_timer.pause()
        else:
            self.visible = True
            self.blink_timer.reset()
            self.blink_timer.resume()
            self.update_follow()


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

    def update_node_styles(self, animate: bool = True) -> None:
        pass


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

    def __init__(self, project_path: Path, agent: AgentData | None = None) -> None:
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
        self._agent_data = agent
        self._agent_fail = False
        self._mouse_down_offset: Offset | None = None

        self._focusable_terminals: list[Terminal] = []

        self.project_data_path = paths.get_project_data(project_path)
        self.shell_history = History(self.project_data_path / "shell_history.jsonl")
        self.prompt_history = History(self.project_data_path / "prompt_history.jsonl")

        self.session_start_time: float | None = None
        self._terminal_count = 0
        self._require_check_prune = False

        self._turn_count = 0
        self._shell_count = 0

        self._directory_changed = False
        self._directory_watcher: DirectoryWatcher | None = None

    @property
    def agent_title(self) -> str | None:
        if self._agent_data is not None:
            return self._agent_data["name"]
        return None

    @property
    def is_watching_directory(self) -> bool:
        """Is the directory watcher enabled and watching?"""
        if self._directory_watcher is None:
            return False
        return self._directory_watcher.enabled

    def validate_shell_history_index(self, index: int) -> int:
        return clamp(index, -self.shell_history.size, 0)

    def validate_prompt_history_index(self, index: int) -> int:
        return clamp(index, -self.prompt_history.size, 0)

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
            and (event.character.isalnum() or event.character in "$/!")
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

        for terminal in reversed(self._focusable_terminals):
            if terminal.display:
                return terminal
        return None

    def add_focusable_terminal(self, terminal: Terminal) -> None:
        """Add a focusable terminal.

        Args:
            terminal: Terminal instance.
        """
        if not terminal.is_finalized:
            self._focusable_terminals.append(terminal)

    @on(DirectoryChanged)
    def on_directory_changed(self, event: DirectoryChanged) -> None:
        event.stop()
        self._directory_changed = True

    @on(Terminal.Finalized)
    def on_terminal_finalized(self, event: Terminal.Finalized) -> None:
        """Terminal was finalized, so we can remove it from the list."""
        try:
            self._focusable_terminals.remove(event.terminal)
        except ValueError:
            pass

        if self._directory_changed or not self.is_watching_directory:
            self.prompt.project_directory_updated()
            self._directory_changed = False
            self.post_message(messages.ProjectDirectoryUpdated())

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
        self.session_start_time = monotonic()
        if self.agent is not None:
            content = Content.assemble(self.agent.get_info(), " connected")
            self.flash(content, style="success")
            if self._agent_data is not None:
                self.app.capture_event(
                    "agent-session-begin",
                    agent=self._agent_data["identity"],
                )

        self.agent_ready = True

    async def on_unmount(self) -> None:
        if self._directory_watcher is not None:
            self._directory_watcher.stop()
        if self.agent is not None:
            await self.agent.stop()

        if self._agent_data is not None and self.session_start_time is not None:
            session_time = monotonic() - self.session_start_time
            await self.app.capture_event(
                "agent-session-end",
                agent=self._agent_data["identity"],
                duration=session_time,
                agent_session_fail=self._agent_fail,
                shell_count=self._shell_count,
                turn_count=self._turn_count,
            ).wait()

    @on(AgentFail)
    async def on_agent_fail(self, message: AgentFail) -> None:
        self.agent_ready = True
        self._agent_fail = True
        self.notify(message.message, title="Agent failure", severity="error", timeout=5)

        if self._agent_data is not None:
            self.app.capture_event(
                "agent-session-error",
                agent=self._agent_data["identity"],
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
            await self.post_shell(event.body)
        elif text := event.body.strip():
            await self.prompt_history.append(event.body)
            self.prompt_history_index = 0
            if text.startswith("/") and await self.slash_command(text):
                # Toad has processed the slash command.
                return
            await self.post(UserInput(text))
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

        if self._directory_changed or not self.is_watching_directory:
            self._directory_changed = False
            self.post_message(messages.ProjectDirectoryUpdated())
            self.prompt.project_directory_updated()

        self._turn_count += 1

        if stop_reason != "end_turn":
            from toad.widgets.markdown_note import MarkdownNote

            agent = (self.agent_title or "agent").title()

            if stop_reason == "max_tokens":
                await self.post(
                    MarkdownNote(
                        STOP_REASON_MAX_TOKENS.replace("$AGENT", agent),
                        classes="-stop-reason",
                    )
                )
            elif stop_reason == "max_turn_requests":
                await self.post(
                    MarkdownNote(
                        STOP_REASON_MAX_TURN_REQUESTS.replace("$AGENT", agent),
                        classes="-stop-reason",
                    )
                )
            elif stop_reason == "refusal":
                await self.post(
                    MarkdownNote(
                        STOP_REASON_REFUSAL.replace("$AGENT", agent),
                        classes="-stop-reason",
                    )
                )

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
        self.working_directory = str(Path(event.path).resolve().absolute())

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    @on(acp_messages.UpdateStatusLine)
    async def on_update_status_line(self, message: acp_messages.UpdateStatusLine):
        self.status = message.status_line

    @on(acp_messages.Update)
    async def on_acp_agent_message(self, message: acp_messages.Update):
        message.stop()
        self._agent_thought = None
        await self.post_agent_response(message.text)

    @on(acp_messages.Thinking)
    async def on_acp_agent_thinking(self, message: acp_messages.Thinking):
        message.stop()
        await self.post_agent_thought(message.text)

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
        terminal = self._terminal
        if terminal is not None and not terminal.is_finalized:
            await self.shell.interrupt()
            # self._shell = None
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

    @on(acp_messages.SetModes)
    async def on_acp_set_modes(self, message: acp_messages.SetModes):
        self.modes = message.modes
        self.current_mode = self.modes[message.current_mode]

    @on(messages.HistoryMove)
    async def on_history_move(self, message: messages.HistoryMove) -> None:
        message.stop()
        if message.shell:
            await self.shell_history.open()

            if self.shell_history_index == 0:
                current_shell_command = ""
            else:
                current_shell_command = (
                    await self.shell_history.get_entry(self.shell_history_index)
                )["input"]
            while True:
                self.shell_history_index += message.direction
                new_entry = await self.shell_history.get_entry(self.shell_history_index)
                if (new_entry)["input"] != current_shell_command:
                    break
                if message.direction == +1 and self.shell_history_index == 0:
                    break
                if (
                    message.direction == -1
                    and self.shell_history_index <= -self.shell_history.size
                ):
                    break
        else:
            await self.prompt_history.open()
            self.prompt_history_index += message.direction

    @work
    async def request_permissions(
        self,
        result_future: Future[Answer],
        options: list[Answer],
        tool_call_update: acp_protocol.ToolCallUpdatePermissionRequest,
    ) -> None:
        kind = tool_call_update.get("kind")

        title: str | None = None
        if kind is None:
            from toad.widgets.tool_call import ToolCall

            if (contents := tool_call_update.get("content")) is not None:
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
        else:
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

        self.agent_info

        if self.agent_title:
            notify_title = f"[{self.agent_title}] {question}"
        else:
            notify_title = question
        notify_message = "\n".join(f" • {option.text}" for option in options)
        self.app.system_notify(notify_message, title=notify_title)

        self.prompt.ask(Ask(question, options, callback))

    def _build_slash_commands(self) -> list[SlashCommand]:
        slash_commands = [
            SlashCommand("/toad:about", "About Toad"),
        ]
        slash_commands.extend(self.agent_slash_commands)
        deduplicated_slash_commands = {
            slash_command.command: slash_command for slash_command in slash_commands
        }
        slash_commands = sorted(
            deduplicated_slash_commands.values(), key=attrgetter("command")
        )
        return slash_commands

    def update_slash_commands(self) -> None:
        """Update slash commands, which may have changed since mounting."""
        self.prompt.slash_commands = self._build_slash_commands()

    async def on_mount(self) -> None:
        self.trap_focus()
        self.prompt.focus()
        self.prompt.slash_commands = self._build_slash_commands()
        self.call_after_refresh(self.post_welcome)
        self.app.settings_changed_signal.subscribe(self, self._settings_changed)

        self.shell_history.complete.add_words(
            self.app.settings.get("shell.allow_commands", expect_type=str).split()
        )
        self.shell
        if self._agent_data is not None:

            def start_agent() -> None:
                """Start the agent after refreshing the UI."""
                assert self._agent_data is not None
                from toad.acp.agent import Agent

                self.agent = Agent(self.project_path, self._agent_data)
                self.agent.start(self)

            self.call_after_refresh(start_agent)

        else:
            self.agent_ready = True

    def _settings_changed(self, setting_item: tuple[str, str]) -> None:
        key, value = setting_item
        if key == "shell.allow_commands":
            self.shell_history.complete.add_words(value.split())

    @work
    async def post_welcome(self) -> None:
        """Post any welcome content."""

    def watch_agent(self, agent: AgentBase | None) -> None:
        if agent is None:
            self.agent_info = Content.styled("shell")
        else:
            self.agent_info = agent.get_info()
            self.agent_ready = False

    async def watch_agent_ready(self, ready: bool) -> None:
        with suppress(asyncio.TimeoutError):
            async with asyncio.timeout(2.0):
                await self.shell.wait_for_ready()
        if ready:
            self._directory_watcher = DirectoryWatcher(self.project_path, self)
            self._directory_watcher.start()
        if ready and (agent_data := self._agent_data) is not None:
            welcome = agent_data.get("welcome", None)
            if welcome is not None:
                from toad.widgets.markdown_note import MarkdownNote

                await self.post(MarkdownNote(welcome))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._mouse_down_offset = event.screen_offset

    def on_click(self, event: events.Click) -> None:
        if (
            self._mouse_down_offset is not None
            and event.screen_offset != self._mouse_down_offset
        ):
            return
        widget = event.widget

        contents = self.contents
        if self.screen.get_selected_text():
            return
        if widget is None or widget.is_maximized:
            return
        try:
            widget.query_ancestor(Prompt)
        except NoMatches:
            pass
        else:
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

    async def post[WidgetType: Widget](
        self, widget: WidgetType, *, anchor: bool = True, loading: bool = False
    ) -> WidgetType:
        if self._loading is not None:
            await self._loading.remove()
        if not self.contents.is_attached:
            return widget

        await self.contents.mount(widget)
        widget.loading = loading
        if anchor:
            self.window.anchor()
        self._require_check_prune = True
        self.call_after_refresh(self.check_prune)
        return widget

    async def check_prune(self) -> None:
        """Check if a prune is required."""
        if self._require_check_prune:
            await self.prune_window(1500, 2500)
            self._require_check_prune = False

    async def prune_window(self, low_mark: int, high_mark: int) -> None:
        """Remove older children to keep within a certain range.

        Args:
            low_mark: Height to aim for.
            high_mark: Height to start pruning.
        """

        assert high_mark >= low_mark

        contents = self.contents
        height = contents.virtual_size.height
        if height <= high_mark:
            return
        prune_children: list[Widget] = []
        bottom_margin = 0
        prune_height = 0
        for child in contents.children:
            if not child.display:
                continue
            top, _, bottom, _ = child.styles.margin
            child_height = child.outer_size.height
            prune_height = (
                (prune_height - bottom_margin + max(bottom_margin, top))
                + bottom
                + child_height
            )
            bottom_margin = bottom
            if height - prune_height <= low_mark:
                break
            prune_children.append(child)

        if prune_children:
            await contents.remove_children(prune_children)

    async def new_terminal(self) -> Terminal:
        """Create a new interactive Terminal.

        Args:
            width: Initial width of the terminal.
            display: Initial display.

        Returns:
            A new (mounted) Terminal widget.
        """
        from toad.widgets.shell_terminal import ShellTerminal

        if (terminal := self._terminal) is not None:
            if terminal.state.buffer.is_blank:
                terminal.finalize()
                await terminal.remove()

        self._terminal_count += 1

        terminal_width, terminal_height = self.get_terminal_dimensions()
        terminal = ShellTerminal(
            f"terminal #{self._terminal_count}",
            size=(terminal_width, terminal_height),
            get_terminal_dimensions=self.get_terminal_dimensions,
        )

        terminal.display = False
        terminal = await self.post(terminal)
        self.add_focusable_terminal(terminal)
        self.refresh_bindings()
        return terminal

    def get_terminal_dimensions(self) -> tuple[int, int]:
        """Get the default dimensions of new terminals.

        Returns:
            Tuple of (WIDTH, HEIGHT)
        """
        terminal_width = max(
            16,
            (self.window.size.width - 2 - self.window.styles.scrollbar_size_vertical),
        )
        terminal_height = max(8, self.window.scrollable_content_region.height - 4)
        return terminal_width, terminal_height

    @property
    def shell(self) -> Shell:
        """A Shell instance."""

        if self._shell is None or self._shell.is_finished:
            shell_command = self.app.settings.get(
                "shell.command",
                str,
                expand=False,
            )
            shell_start = self.app.settings.get(
                "shell.command_start",
                str,
                expand=False,
            )
            shell_directory = self.working_directory
            self._shell = Shell(
                self, shell_directory, shell=shell_command, start=shell_start
            )
            self._shell.start()
        return self._shell

    async def post_shell(self, command: str) -> None:
        """Post a command to the shell.

        Args:
            command: Command to execute.
        """
        from toad.widgets.shell_result import ShellResult

        if command.strip():
            self._shell_count += 1
            await self.post(ShellResult(command))
            width, height = self.get_terminal_dimensions()
            await self.shell.send(command, width, height)

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

    @work
    async def action_cancel(self) -> None:
        if monotonic() - self._last_escape_time < 3:
            if (agent := self.agent) is not None:
                if await agent.cancel():
                    self.flash("Turn cancelled", style="success")
                else:
                    self.flash("Agent declined to cancel. Please wait.", style="error")
        else:
            self.flash("Press [b]esc[/] again to cancel agent's turn")
            self._last_escape_time = monotonic()

    def focus_prompt(self, reset_cursor: bool = True, scroll_end: bool = True) -> None:
        """Focus the prompt input.

        Args:
            reset_cursor: Reset the block cursor.
            scroll_end: Scroll t the end of the content.
        """
        if reset_cursor:
            self.cursor_offset = -1
            self.cursor.visible = False
        if scroll_end:
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
        else:
            menu = Menu(block, menu_options)

        menu.offset = Offset(1, block.region.offset.y)
        await self.mount(menu)
        menu.focus()

    def action_copy_to_clipboard(self) -> None:
        block = self.get_cursor_block()
        if isinstance(block, MenuProtocol):
            text = block.get_block_content("clipboard")
        elif isinstance(block, MarkdownFence):
            text = block._content.plain
        elif isinstance(block, MarkdownBlock):
            text = block.source
        else:
            return
        if text:
            self.app.copy_to_clipboard(text)
            self.flash("Copied to clipboard")

    def action_copy_to_prompt(self) -> None:
        block = self.get_cursor_block()
        if isinstance(block, MenuProtocol):
            text = block.get_block_content("prompt")
        elif isinstance(block, MarkdownFence):
            # Copy to prompt leaves MD formatting
            text = block.source
        elif isinstance(block, MarkdownBlock):
            text = block.source
        else:
            return

        if text:
            self.prompt.append(text)
            self.flash("Copied to prompt")
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

    async def action_mode_switcher(self) -> None:
        self.prompt.mode_switcher.focus()

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
        self.refresh_bindings()

    async def slash_command(self, text: str) -> bool:
        """Give Toad the opertunity to process slash commands.

        Args:
            text: The prompt, including the slash in the first position.

        Returns:
            `True` if Toad has processed the slash command, `False` if it should
                be forwarded to the agent.
        """
        command, _, parameters = text[1:].partition(" ")
        if command == "toad:about":
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
        return False
