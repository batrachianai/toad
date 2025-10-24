import re
from typing import Iterable
from rich.text import Text

from textual import on
from textual import events
from textual.app import ComposeResult

from textual.content import Content
from textual.reactive import var
from textual.css.query import NoMatches
from textual import containers
from textual.widgets import Static, Markdown

from toad.app import ToadApp
from toad.acp import protocol
from toad.menus import MenuItem
from toad.pill import pill


class TextContent(Static):
    DEFAULT_CSS = """
    TextContent 
    {
        height: auto;
    }
    """


class MarkdownContent(Markdown):
    pass


class ToolCallItem(containers.HorizontalGroup):
    def compose(self) -> ComposeResult:
        yield Static(classes="icon")


class ToolCallDiff(Static):
    DEFAULT_CSS = """
    ToolCallDiff {
        height: auto;
    }
    """


class ToolCallHeader(Static):
    ALLOW_SELECT = False
    DEFAULT_CSS = """
    ToolCallHeader {
        width: auto;        
        &:hover {
            background: $panel;
        }
    }
    """


class ToolCall(containers.VerticalGroup):
    DEFAULT_CLASSES = "block"
    DEFAULT_CSS = """
    ToolCall {
        padding: 0 1;
        # background: $foreground 5%;
        # border-top: panel black 10%;
        width: 1fr;
        layout: stream;
        height: auto;

        .icon {
            width: auto;
            margin-right: 1;
        }
        #tool-content {
            margin-top: 1;
            # &:empty {
            #     display: none;
            # }
            display: none;
        }
        &.-expanded {
            #tool-content {
                display: block;
            }
        }
    }

    """

    has_content: var[bool] = var(False)
    expanded: var[bool] = var(False, toggle_class="-expanded")

    def __init__(
        self,
        tool_call: protocol.ToolCall,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._tool_call = tool_call
        super().__init__(id=id, classes=classes)

    @property
    def tool_call(self) -> protocol.ToolCall:
        return self._tool_call

    @tool_call.setter
    def tool_call(self, tool_call: protocol.ToolCall):
        self._tool_call = tool_call
        self.refresh(recompose=True)

    def get_block_menu(self) -> Iterable[MenuItem]:
        if self.expanded:
            yield MenuItem("Collapse", "block.collapse", "x")
        else:
            yield MenuItem("Expand", "block.expand", "x")

    def action_collapse(self) -> None:
        self.expanded = False

    def action_expand(self) -> None:
        self.expanded = True

    def get_block_content(self, destination: str) -> str | None:
        return None

    def can_expand(self) -> bool:
        return self.has_content

    def expand_block(self) -> None:
        self.expanded = True

    def collapse_block(self) -> None:
        self.expanded = False

    def is_block_expanded(self) -> bool:
        return self.expanded

    def compose(self) -> ComposeResult:
        tool_call = self._tool_call
        content: list[protocol.ToolCallContent] = tool_call.get("content", None) or []
        self.has_content = bool(content)
        title = tool_call.get("title", "title")

        yield ToolCallHeader(self.tool_call_header_content, markup=False).with_tooltip(
            title
        )
        with containers.VerticalGroup(id="tool-content"):
            yield from self._compose_content(content)

    @property
    def tool_call_header_content(self) -> Content:
        tool_call = self._tool_call
        kind = tool_call.get("kind", "tool")
        title = tool_call.get("title", "title")
        status = tool_call.get("status", "pending")

        expand_icon: Content = Content.styled("▶ ", "$text 40%")
        if self.has_content:
            if self.expanded:
                expand_icon = Content("▼ ")
            else:
                expand_icon = Content("▶ ")

        header = Content.assemble(
            expand_icon,
            "🔧 ",
            pill(kind, "$primary-muted", "$text-primary"),
            " ",
            (title, "$text-success"),
        )
        if status == "pending":
            header += Content.assemble(" ⏲")
        elif status == "in_progress":
            pass
        elif status == "failed":
            header += Content.assemble(" ", pill("failed", "$error-muted", "$error"))
        elif status == "completed":
            header += Content.from_markup(" [$success]✔")
        return header

    def watch_expanded(self) -> None:
        try:
            self.query_one(ToolCallHeader).update(self.tool_call_header_content)
        except NoMatches:
            pass

    def watch_has_content(self) -> None:
        try:
            self.query_one(ToolCallHeader).update(self.tool_call_header_content)
        except NoMatches:
            pass

    @on(events.Click, "ToolCallHeader")
    def on_click_tool_call_header(self, event: events.Click) -> None:
        event.stop()
        if self.has_content:
            self.expanded = not self.expanded
        else:
            self.app.bell()

    def _compose_content(
        self, tool_call_content: list[protocol.ToolCallContent]
    ) -> ComposeResult:
        def compose_content_block(
            content_block: protocol.ContentBlock,
        ) -> ComposeResult:
            match content_block:
                # TODO: This may need updating
                # Docs claim this should be "plain" text
                # However, I have seen simple text, text with ansi escape sequences, and Markdown returned
                # I think this is a flaw in the spec.
                # For now I will attempt a heuristic to guess what the content actually contains
                # https://agentclientprotocol.com/protocol/schema#param-text
                case {"type": "text", "text": text}:
                    if "\x1b" in text:
                        parsed_ansi_text = Text.from_ansi(text)
                        yield TextContent(Content.from_rich_text(parsed_ansi_text))
                    elif "```" in text or re.search(
                        r"^#{1,6}\s.*$", text, re.MULTILINE
                    ):
                        yield MarkdownContent(text)
                    else:
                        yield TextContent(text, markup=False)

        for content in tool_call_content:
            match content:
                case {"type": "content", "content": sub_content}:
                    yield from compose_content_block(sub_content)
                case {
                    "type": "diff",
                    "path": path,
                    "oldText": old_text,
                    "newText": new_text,
                }:
                    from toad.widgets.diff_view import DiffView

                    yield (diff_view := DiffView(path, path, old_text or "", new_text))

                    if isinstance(self.app, ToadApp):
                        diff_view_setting = self.app.settings.get("diff.view", str)
                        diff_view.split = diff_view_setting == "split"
                        diff_view.auto_split = diff_view_setting == "auto"

                case {"type": "terminal", "terminalId": terminal_id}:
                    pass


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    TOOL_CALL_READ: protocol.ToolCall = {
        "sessionUpdate": "tool_call",
        "toolCallId": "write_file-1759480341499",
        "status": "completed",
        "title": "Foo",
        "content": [
            {
                "type": "diff",
                "path": "fib.py",
                "oldText": "",
                "newText": 'def fibonacci(n):\n    """Generates the Fibonacci sequence up to n terms."""\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b\n\nif __name__ == "__main__":\n    for number in fibonacci(10):\n        print(number)\n',
            }
        ],
    }

    TOOL_CALL_CONTENT: protocol.ToolCall = {
        "sessionUpdate": "tool_call",
        "toolCallId": "run_shell_command-1759480356886",
        "status": "completed",
        "title": "Bar",
        "content": [
            {
                "type": "content",
                "content": {
                    "type": "text",
                    "text": "0\n1\n1\n2\n3\n5\n8\n13\n21\n34",
                },
            }
        ],
    }

    TOOL_CALL_EMPTY: protocol.ToolCall = {
        "sessionUpdate": "tool_call",
        "toolCallId": "run_shell_command-1759480356886",
        "status": "completed",
        "title": "Bar",
        "content": [],
    }

    class ToolApp(App):
        def on_mount(self) -> None:
            self.theme = "dracula"

        def compose(self) -> ComposeResult:
            yield ToolCall(TOOL_CALL_READ)
            yield ToolCall(TOOL_CALL_CONTENT)
            yield ToolCall(TOOL_CALL_EMPTY)

    ToolApp().run()
