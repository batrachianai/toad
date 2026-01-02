from pathlib import Path

from textual.reactive import var
from textual import work
from textual.widget import Widget
from textual.widgets import Markdown
from textual.widgets.markdown import MarkdownStream

from toad import messages
from toad.rtl import apply_bidi_to_markdown


SYSTEM = """\
If asked to output code add inline documentation in the google style format, and always use type hinting where appropriate.
Avoid using external libraries where possible, and favor code that writes output to the terminal.
When asked for a table do not wrap it in a code fence.
"""


class AgentResponse(Markdown):
    block_cursor_offset = var(-1)

    def __init__(self, markdown: str | None = None) -> None:
        # Apply RTL support for Hebrew, Arabic, and other BiDi languages
        if markdown is not None:
            markdown = apply_bidi_to_markdown(markdown)
        super().__init__(markdown)
        self._stream: MarkdownStream | None = None
        self._rtl_buffer: str = ""  # Buffer for incomplete lines during streaming

    def block_cursor_clear(self) -> None:
        self.block_cursor_offset = -1

    def block_cursor_up(self) -> Widget | None:
        if self.block_cursor_offset == -1:
            if self.children:
                self.block_cursor_offset = len(self.children) - 1
            else:
                return None
        else:
            self.block_cursor_offset -= 1

        if self.block_cursor_offset == -1:
            return None
        try:
            return self.children[self.block_cursor_offset]
        except IndexError:
            self.block_cursor_offset = -1
            return None

    def block_cursor_down(self) -> Widget | None:
        if self.block_cursor_offset == -1:
            if self.children:
                self.block_cursor_offset = 0
            else:
                return None
        else:
            self.block_cursor_offset += 1
        if self.block_cursor_offset >= len(self.children):
            self.block_cursor_offset = -1
            return None
        try:
            return self.children[self.block_cursor_offset]
        except IndexError:
            self.block_cursor_offset = -1
            return None

    def get_cursor_block(self) -> Widget | None:
        if self.block_cursor_offset == -1:
            return None
        return self.children[self.block_cursor_offset]

    def block_select(self, widget: Widget) -> None:
        self.block_cursor_offset = self.children.index(widget)

    @property
    def stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = self.get_stream(self)
        return self._stream

    async def append_fragment(self, fragment: str) -> None:
        self.loading = False
        # Buffer fragments and only apply BiDi to complete lines
        # This prevents the BiDi algorithm from corrupting partial lines during streaming
        text = self._rtl_buffer + fragment

        if "\n" in text:
            # Split into complete lines and remainder
            lines = text.split("\n")
            complete_lines = lines[:-1]  # All but last are complete
            self._rtl_buffer = lines[-1]  # Last line may be incomplete

            # Apply BiDi only to complete lines
            processed = "\n".join(complete_lines) + "\n"
            processed = apply_bidi_to_markdown(processed)
            await self.stream.write(processed)
        else:
            # No complete line yet, just buffer
            self._rtl_buffer = text

    async def flush_rtl_buffer(self) -> None:
        """Flush any remaining buffered RTL content."""
        if self._rtl_buffer:
            processed = apply_bidi_to_markdown(self._rtl_buffer)
            await self.stream.write(processed)
            self._rtl_buffer = ""
