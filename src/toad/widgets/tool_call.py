from rich.text import Text

from textual import log
from textual.app import ComposeResult
from textual.content import Content
from textual import containers
from textual.widgets import Static, Markdown

from toad.acp import protocol
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
    DEFAULT_CSS = """
    ToolCallHeader {
        width: 1fr;        
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
            &:empty {
                display: none;
            }
        }
    }

    """

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

    def compose(self) -> ComposeResult:
        tool_call = self._tool_call
        content: list[protocol.ToolCallContent] = tool_call.get("content", None) or []
        kind = tool_call.get("kind", "tool")
        title = tool_call.get("title", "title")
        status = tool_call.get("status", "pending")
        header = Content.assemble(
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

        yield ToolCallHeader(header).with_tooltip(title)
        with containers.VerticalGroup(id="tool-content"):
            yield from self._compose_content(content)

    def _compose_content(
        self, tool_call_content: list[protocol.ToolCallContent]
    ) -> ComposeResult:
        def compose_content_block(
            content_block: protocol.ContentBlock,
        ) -> ComposeResult:
            match content_block:
                case {"type": "text", "text": text}:
                    if "\x1b" in text:
                        text = Text.from_ansi(text)
                        yield TextContent(Content.from_rich_text(text))
                    else:
                        yield TextContent(text)

        for content in tool_call_content:
            log(content)
            match content:
                case {"type": "content", "content": sub_content}:
                    yield from compose_content_block(sub_content)
                case {"type": "diff", "path": path}:
                    pass
                    # yield ToolCallDiff(path, markup=False)
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

    class ToolApp(App):
        def on_mount(self) -> None:
            self.theme = "dracula"

        def compose(self) -> ComposeResult:
            yield ToolCall(TOOL_CALL_READ)
            yield ToolCall(TOOL_CALL_CONTENT)

    ToolApp().run()
