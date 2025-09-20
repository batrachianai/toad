from __future__ import annotations


from functools import cached_property
from typing import TYPE_CHECKING
from pathlib import Path

from typing import Callable, Any

from textual import on, work
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual import events
from textual.binding import Binding
from textual.content import Content
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets.markdown import MarkdownBlock, MarkdownFence
from textual.geometry import Offset, Spacing
from textual.reactive import var, Initialize
from textual.layouts.grid import GridLayout
from textual.layout import WidgetPlacement


import llm

from toad import messages
from toad.acp import messages as acp_messages
from toad.app import ToadApp
from toad.acp import protocol as acp_protocol
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
    from toad.widgets.question import Answer

MD = """\
# Textual Markdown Browser - Demo

This Markdown file contains some examples of Markdown widgets.

## Headers

Headers levels 1 through 6 are supported.

### This is H3

This is H3 Content

#### This is H4

Header level 4 content. Drilling down into finer headings.

##### This is H5

Header level 5 content.

###### This is H6

Header level 6 content.

## Typography

The usual Markdown typography is supported. The exact output depends on your terminal, although most are fairly consistent.

### Emphasis

Emphasis is rendered with `*asterisks*`, and looks *like this*;

### Strong

Use two asterisks to indicate strong which renders in bold, e.g. `**strong**` render **strong**.

### Strikethrough

Two tildes indicates strikethrough, e.g. `~~cross out~~` render ~~cross out~~.

### Inline code ###

Inline code is indicated by backticks. e.g. `import this`.

## Horizontal rule

Draw a horizontal rule with three dashes (`---`).

---

Good for natural breaks in the content, that don't require another header.

[like this][example]

## Lists

1. Lists can be ordered
2. Lists can be unordered
   - I must not fear.
     - Fear is the mind-killer.
       - Fear is the little-death that brings total obliteration.
         - I will face my fear.
           - I will permit it to pass over me and through me.
     - And when it has gone past, I will turn the inner eye to see its path.
   - Where the fear has gone there will be nothing. Only I will remain.

[example]: example.com
   
### Longer list

1. **Duke Leto I Atreides**, head of House Atreides
2. **Lady Jessica**, Bene Gesserit and concubine of Leto, and mother of Paul and Alia
3. **Paul Atreides**, son of Leto and Jessica
4. **Alia Atreides**, daughter of Leto and Jessica
5. **Gurney Halleck**, troubadour warrior of House Atreides
6. **Thufir Hawat**, Mentat and Master of Assassins of House Atreides
7. **Duncan Idaho**, swordmaster of House Atreides
8. **Dr. Wellington Yueh**, Suk doctor of House Atreides
9. **Leto**, first son of Paul and Chani who dies as a toddler
10. **Esmar Tuek**, a smuggler on Arrakis
11. **Staban Tuek**, son of Esmar

## Fences

Fenced code blocks are introduced with three back-ticks and the optional parser. Here we are rendering the code in a sub-widget with syntax highlighting and indent guides.

In the future I think we could add controls to export the code, copy to the clipboard. Heck, even run it and show the output?

```python
@lru_cache(maxsize=1024)
def split(self, cut_x: int, cut_y: int) -> tuple[Region, Region, Region, Region]:
    \"\"\"Split a region into 4 from given x and y offsets (cuts).

    ```
                cut_x ↓
            ┌────────┐ ┌───┐
            │        │ │   │
            │    0   │ │ 1 │
            │        │ │   │
    cut_y → └────────┘ └───┘
            ┌────────┐ ┌───┐
            │    2   │ │ 3 │
            └────────┘ └───┘
    ```

    Args:
        cut_x (int): Offset from self.x where the cut should be made. If negative, the cut
            is taken from the right edge.
        cut_y (int): Offset from self.y where the cut should be made. If negative, the cut
            is taken from the lower edge.

    Returns:
        tuple[Region, Region, Region, Region]: Four new regions which add up to the original (self).
    \"\"\"

    x, y, width, height = self
    if cut_x < 0:
        cut_x = width + cut_x
    if cut_y < 0:
        cut_y = height + cut_y

    _Region = Region
    return (
        _Region(x, y, cut_x, cut_y),
        _Region(x + cut_x, y, width - cut_x, cut_y),
        _Region(x, y + cut_y, cut_x, height - cut_y),
        _Region(x + cut_x, y + cut_y, width - cut_x, height - cut_y),
    )
```

## Quote

Quotes are introduced with a chevron, and render like this:

> I must not fear.
> Fear is the mind-killer.
> Fear is the little-death that brings total obliteration.
> I will face my fear.
> I will permit it to pass over me and through me.
> And when it has gone past, I will turn the inner eye to see its path.
> Where the fear has gone there will be nothing. Only I will remain."

Quotes nest nicely. Here's what quotes within quotes look like:

> I must not fear.
> > Fear is the mind-killer.
> > Fear is the little-death that brings total obliteration.
> > I will face my fear.
> > > I will permit it to pass over me and through me.
> > > And when it has gone past, I will turn the inner eye to see its path.
> > > Where the fear has gone there will be nothing. Only I will remain.

## Tables

Tables are supported, and render as a Rich table.

I would like to add controls to these widgets to export the table as CSV, which I think would be a nice feature. In the future we might also have sortable columns by clicking on the headers.


| Name            | Type   | Default | Description                        |
| --------------- | ------ | ------- | ---------------------------------- |
| `show_header`   | `bool` | `True`  | Show the **table** header              |
| `fixed_rows`    | `int`  | `0`     | Number of fixed rows               |
| `fixed_columns` | `int`  | `0`     | Number of fixed columns            |
| `zebra_stripes` | `bool` | `False` | Display alternating colors on rows |
| `header_height` | `int`  | `1`     | Height of header row               |
| `show_cursor`   | `bool` | `True`  | Show a cell cursor                 |
"""

# MD = """
# ## Tables

# Tables are supported, and render as a Rich table.

# I would like to add controls to these widgets to export the table as CSV, which I think would be a nice feature. In the future we might also have sortable columns by clicking on the headers.

# `FOO`

# | Name            | Type   | Default | Description                        |
# | --------------- | ------ | ------- | ---------------------------------- |
# | `show_header`   | `bool` | `True`  | Show the **table** header              |
# | `fixed_rows`    | `int`  | `0`     | Number of fixed rows               |
# | `fixed_columns` | `int`  | `0`     | Number of fixed columns            |
# | `zebra_stripes` | `bool` | `False` | Display alternating colors on rows |
# | `header_height` | `int`  | `1`     | Height of header row               |
# | `show_cursor`   | `bool` | `True`  | Show a cell cursor                 |
# """

# MD = """
# ```python
# for n in range(10):
#     print(n)
# """

# MD = """
# 1. Lists can be ordered
# 2. Lists can be `unordered`
#    - I must not *fear*.
#      - Fear is the `mind-killer`.
#        - Fear is the little-death that brings total obliteration.
#          - I will face my fear.
#            - I will permit it to pass over me and through me.
#      - And when it has gone past, I will turn the inner eye to see its path.
#    - Where the fear has gone there will be nothing. Only I will remain.
# """

MD = """
```python
def mandelbrot(c: complex, max_iter: int) -> int:
    \"\"\"Determine the number of iterations for a point in the Mandelbrot set.

    Args:
        c (complex): The complex point to test.
        max_iter (int): The maximum number of iterations to test.

    Returns:
        int: Number of iterations before escape or max_iter.
    \"\"\"
    z = 0 + 0j
    for n in range(max_iter):
        if abs(z) > 2:
            return n
        z = z * z + c
    return max_iter

def colorize(iter_count: int, max_iter: int) -> str:
    \"\"\"Get an ANSI color code based on the iteration count.

    Args:
        iter_count (int): Number of iterations completed before escape.
        max_iter (int): Maximum number of iterations allowed.

    Returns:
        str: ANSI escape code for color.
    \"\"\"
    if iter_count == max_iter:
        return "\\033[48;5;0m"  # Black background for points in the set
    else:
        # Create a gradient from 17 to 231 (blue to red) for escaping points
        color_code = 17 + int((iter_count / max_iter) * 214)
        return f"\\033[48;5;{color_code}m"

def draw_mandelbrot(width: int, height: int, max_iter: int) -> None:
    \"\"\"Draw the Mandelbrot set in the terminal using ANSI colors.

    Args:
        width (int): Width of the output in terminal characters.
        height (int): Height of the output in terminal rows.
        max_iter (int): Maximum number of iterations for Mandelbrot calculation.
    \"\"\"
    for y in range(height):
        for x in range(width):
            # Map the (x, y) pixel to a point in the complex plane
            real = (x / width) * 3.5 - 2.5
            imag = (y / height) * 2.0 - 1.0
            c = complex(real, imag)
            
            # Calculate the number of iterations
            iter_count = mandelbrot(c, max_iter)
            
            # Get the color for this point and print a space (box)
            color = colorize(iter_count, max_iter)
            print(f"{color}  ", end="")

        # Reset color and move to the next line
        print("\\033[0m")

# Configuration for drawing
width = 80    # Number of characters wide
height = 40   # Number of character rows
max_iter = 100  # Maximum iterations for Mandelbrot calculation

# Draw the Mandelbrot set
draw_mandelbrot(width, height, max_iter)
```
"""


class Cursor(Static):
    follow_widget: var[Widget | None] = var(None)
    blink = var(True, toggle_class="-blink")

    def on_mount(self) -> None:
        self.display = False
        self.blink_timer = self.set_interval(0.5, self._update_blink, pause=True)
        self.set_interval(0.4, self._update_follow)

    def _update_blink(self) -> None:
        if self.query_ancestor(Window).has_focus:
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
    BINDINGS = [Binding("end", "screen.focus_prompt", "Focus prompt")]


class Conversation(containers.Vertical):
    BINDING_GROUP_TITLE = "Conversation"
    CURSOR_BINDING_GROUP = Binding.Group(description="Block cursor")
    BINDINGS = [
        Binding(
            "alt+up",
            "cursor_up",
            "Block up",
            priority=True,
            group=CURSOR_BINDING_GROUP,
        ),
        Binding(
            "alt+down",
            "cursor_down",
            "Block down",
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

        if self._agent_thought is None:
            self._agent_thought = AgentThought("")
            await self.post(self._agent_thought, loading=True)
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

                # agent_response = AgentResponse(self.conversation)
                # self.agent_response = agent_response
                # await self.post(agent_response, loading=True)
                await self.get_agent_thought()
                # await self.get_agent_response()
                self.send_prompt_to_agent(text)

                # agent_response.send_prompt(
                #     event.body,
                #     Path(self.prompt.current_directory.path).expanduser().absolute(),
                # )

    @work
    async def send_prompt_to_agent(self, prompt: str) -> None:
        if self.agent is not None:
            self.busy_count += 1
            try:
                stop_reason = await self.agent.send_prompt(prompt)
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
        self.window.focus(scroll_visible=False)
        await event.menu.remove()

        if event.action is not None:
            await self.run_action(event.action, {"block": event.owner})
        # await event.menu.remove()
        # self.cursor.visible = True

    # @on(events.DescendantFocus)
    # def on_descendant_focus(self, event: events.DescendantFocus):
    #     if isinstance(event.widget, HighlightedTextArea):
    #         self.cursor_offset = -1

    # @on(events.DescendantBlur)
    # def on_descendant_blur(self, event: events.DescendantBlur):
    #     if isinstance(event.widget, Window):
    #         self.cursor.visible = False

    @on(Menu.Dismissed)
    async def on_menu_dismissed(self, event: Menu.Dismissed) -> None:
        event.stop()
        # self.cursor.visible = True

        # with self.window.prevent(events.DescendantFocus):
        #     self.window.focus(scroll_visible=False)

        self.window.focus(scroll_visible=False)
        await event.menu.remove()
        # self.cursor.visible = True

    @on(CurrentWorkingDirectoryChanged)
    def on_current_working_directory_changed(
        self, event: CurrentWorkingDirectoryChanged
    ) -> None:
        self.prompt.current_directory.path = event.path

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    @on(acp_messages.ACPUpdate)
    async def on_acp_agent_message(self, message: acp_messages.ACPUpdate):
        message.stop()
        if self._agent_thought and self._agent_thought.loading:
            await self._agent_thought.remove()
        agent_response = await self.get_agent_response()
        await agent_response.append_fragment(message.text)

    @on(acp_messages.ACPThinking)
    async def on_acp_agent_thinking(self, message: acp_messages.ACPThinking):
        message.stop()
        agent_thought = await self.get_agent_thought()
        await agent_thought.append_fragment(message.text)

    @on(acp_messages.ACPRequestPermission)
    async def on_acp_request_permission(
        self, message: acp_messages.ACPRequestPermission
    ):
        from toad.widgets.question import Answer

        message.stop()
        await self.post_tool_call(message.tool_call)
        self.ask(
            [
                Answer(
                    option["name"],
                    option["optionId"],
                )
                for option in message.options
            ],
            callback=message.result_future.set_result,
        )

    async def post_tool_call(
        self, tool_call_update: acp_protocol.ToolCallUpdate
    ) -> None:
        self.log("post_tool_call")
        self.log(tool_call_update)
        if not isinstance((contents := tool_call_update.get("content", None)), list):
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

    async def post_diff(self, path: str, before: str, after: str) -> None:
        """Post a diff view.

        Args:
            path: Path to the file.
            before: Content of file before edit.
            after: Content of file after edit.
        """
        from toad.widgets.diff_view import DiffView

        diff_view = DiffView(path, path, before, after, classes="block")
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

    async def on_mount(self) -> None:
        self.prompt.focus()
        self.prompt.slash_commands = [
            SlashCommand("/about", "About Toad"),
            SlashCommand("/help", "Open Help"),
            SlashCommand("/set", "Change a setting"),
        ]
        self.call_after_refresh(self.post_welcome)
        self.app.settings_changed_signal.subscribe(self, self._settings_changed)
        self.start_shell()

        if self.app.acp_command is not None:
            from toad.acp.agent import Agent

            self.agent = Agent(self.project_path, self.app.acp_command)
            self.agent.start(self)

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
        if widget is None:
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

    async def get_ansi_log(self, width: int) -> ANSILog:
        from toad.widgets.ansi_log import ANSILog

        if self.children and isinstance(self.children[-1], ANSILog):
            ansi_log = self.children[-1]
        else:
            ansi_log = await self.post(ANSILog(minimum_terminal_width=width))
            await ansi_log.wait_for_refresh()
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
            MenuItem("Copy to clipboard", "copy_to_clipboard", "c"),
            MenuItem("Copy to prompt", "copy_to_prompt", "p"),
        ]

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
            self.notify("This block has no menu", title="Menu", severity="information")
            self.app.bell()
            return

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
            self.call_after_refresh(self.window.scroll_to_center, cursor_block)
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
