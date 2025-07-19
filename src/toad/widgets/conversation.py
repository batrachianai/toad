from functools import partial
from textual import on
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Markdown, Static
from textual.widgets._markdown import MarkdownBlock
from textual.geometry import Offset
from textual.timer import Timer

from textual.reactive import var


from toad import messages
from toad.widgets.menu import Menu
from toad.widgets.prompt import Prompt
from toad.widgets.throbber import Throbber
from toad.widgets.welcome import Welcome
from toad.widgets.user_input import UserInput
from toad.widgets.agent_response import AgentResponse


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
| `show_header`   | `bool` | `True`  | Show the table header              |
| `fixed_rows`    | `int`  | `0`     | Number of fixed rows               |
| `fixed_columns` | `int`  | `0`     | Number of fixed columns            |
| `zebra_stripes` | `bool` | `False` | Display alternating colors on rows |
| `header_height` | `int`  | `1`     | Height of header row               |
| `show_cursor`   | `bool` | `True`  | Show a cell cursor                 |
"""


class Cursor(Static):
    follow_widget: var[Widget | None] = var(None)
    blink = var(True, toggle_class="-blink")

    def on_mount(self) -> None:
        self.display = False
        self.blink_timer = self.set_interval(0.5, self._update_blink, pause=True)
        self.set_interval(0.2, self._update_follow)

    def _update_blink(self) -> None:
        self.blink = not self.blink

    def watch_follow_widget(self, widget: Widget | None) -> None:
        self.display = widget is not None

    def _update_follow(self) -> None:
        if self.follow_widget:
            self.styles.height = max(1, self.follow_widget.size.height)
            follow_y = self.follow_widget.region.y
            self.offset = Offset(0, follow_y + self.container_scroll_offset.y)

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


class Contents(containers.VerticalScroll):
    BINDING_GROUP_TITLE = "View"


class Conversation(containers.Vertical):
    BINDING_GROUP_TITLE = "Conversation"
    BINDINGS = [
        Binding("shift+up", "cursor_up", "Block cursor up", priority=True),
        Binding("shift+down", "cursor_down", "Block cursor down", priority=True),
        Binding("escape", "dismiss", "Dismiss"),
    ]

    busy_count = var(0)
    block_cursor = var(-1)
    blocks: var[list[Widget]] = var(list)

    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    contents = getters.query_one("#contents", containers.VerticalScroll)
    cursor = getters.query_one(Cursor)
    prompt = getters.query_one(Prompt)

    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        yield Menu(
            [
                Menu.Item("a", "Do an A thing", key="a"),
                Menu.Item("b", "Do an B thing", key="b"),
                Menu.Item("c", "Copy to Clipboard", key="c"),
                Menu.Item("x", "Expand details", key="x"),
                Menu.Item("c", "This doesn't have a key, but does have a long label"),
            ]
        )
        with Contents(id="contents"):
            yield Cursor()
        yield Prompt()

    @on(messages.WorkStarted)
    def on_work_started(self) -> None:
        self.busy_count += 1

    @on(messages.WorkFinished)
    def on_work_finished(self) -> None:
        self.busy_count -= 1

    @on(messages.UserInputSubmitted)
    async def on_user_input_submitted(self, event: messages.UserInputSubmitted) -> None:
        await self.post(UserInput(event.body))
        agent_response = AgentResponse()
        await self.post(agent_response)
        agent_response.send_prompt(event.body)

    def watch_busy_count(self, busy: int) -> None:
        self.throbber.set_class(busy > 0, "-busy")

    async def on_mount(self) -> None:
        self.contents.anchor()
        await self.post(Welcome())
        agent_response = AgentResponse()
        await self.post(agent_response)
        agent_response.update(MD)
        self.screen.can_focus = False
        self.prompt.focus()

    async def post(self, widget: Widget) -> None:
        await self.contents.mount(widget)
        self.contents.anchor()

    def action_cursor_up(self) -> None:
        self.blocks = list(
            self.query("Markdown > MarkdownBlock").results(MarkdownBlock)
        )
        if self.block_cursor < 0:
            self.block_cursor = len(self.blocks) - 1
        else:
            self.block_cursor -= 1

    def action_cursor_down(self) -> None:
        self.blocks = list(
            self.query("Markdown > MarkdownBlock").results(MarkdownBlock)
        )
        if self.block_cursor == -1:
            self.block_cursor = len(self.blocks) - 1
        elif self.block_cursor < len(self.blocks) - 1:
            self.block_cursor += 1

    def action_dismiss(self) -> None:
        self.block_cursor = -1

    def watch_block_cursor(self, block_cursor: int) -> None:
        if block_cursor == -1:
            self.cursor.follow(None)
            self.contents.scroll_end(immediate=True)
            self.prompt.focus()
        else:
            # self.contents.focus()
            blocks = list(self.query("Markdown > MarkdownBlock").results(MarkdownBlock))
            block = blocks[block_cursor]
            # self.notify(block.source)
            self.cursor.follow(block)
            self.contents.release_anchor()
            self.contents.scroll_to_center(blocks[block_cursor], immediate=True)
