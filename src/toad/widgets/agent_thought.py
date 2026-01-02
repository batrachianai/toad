from __future__ import annotations
from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.reactive import var
from textual.widgets import Markdown
from textual.widgets.markdown import MarkdownStream

from toad.rtl import apply_bidi_to_markdown


class AgentThought(Markdown, can_focus=True):
    """The agent's 'thoughts'."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("left", "scroll_left", "Scroll Left", show=False),
        Binding("right", "scroll_right", "Scroll Right", show=False),
        Binding("home", "scroll_home", "Scroll Home", show=False),
        Binding("end", "scroll_end", "Scroll End", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("ctrl+pageup", "page_left", "Page Left", show=False),
        Binding("ctrl+pagedown", "page_right", "Page Right", show=False),
    ]

    ALLOW_MAXIMIZE = True
    _stream: var[MarkdownStream | None] = var(None)

    def __init__(
        self,
        markdown: str | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        # Apply RTL support for Hebrew, Arabic, and other BiDi languages
        if markdown is not None:
            markdown = apply_bidi_to_markdown(markdown)
        super().__init__(markdown, name=name, id=id, classes=classes)
        self._rtl_buffer: str = ""  # Buffer for incomplete lines during streaming

    def watch_loading(self, loading: bool) -> None:
        self.set_class(loading, "-loading")

    @property
    def stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = self.get_stream(self)
        return self._stream

    async def append_fragment(self, fragment: str) -> None:
        self.loading = False
        # Buffer fragments and only apply BiDi to complete lines
        text = self._rtl_buffer + fragment

        if "\n" in text:
            lines = text.split("\n")
            complete_lines = lines[:-1]
            self._rtl_buffer = lines[-1]

            processed = "\n".join(complete_lines) + "\n"
            processed = apply_bidi_to_markdown(processed)
            await self.stream.write(processed)
        else:
            self._rtl_buffer = text
        self.scroll_end()

    async def flush_rtl_buffer(self) -> None:
        """Flush any remaining buffered RTL content."""
        if self._rtl_buffer:
            processed = apply_bidi_to_markdown(self._rtl_buffer)
            await self.stream.write(processed)
            self._rtl_buffer = ""
