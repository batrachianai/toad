from __future__ import annotations
from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.reactive import var
from textual.widgets import Markdown
from textual.widgets.markdown import MarkdownStream


class AgentThought(Markdown, can_focus=True):
    """The agent's 'thoughts'."""

    HELP = """
## Agent thoughts

- **cursor keys** Scroll text
"""

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

    def watch_loading(self, loading: bool) -> None:
        self.set_class(loading, "-loading")

    def on_mount(self) -> None:
        self.scroll_end()

    @property
    def stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = self.get_stream(self)
        return self._stream

    async def append_fragment(self, fragment: str) -> None:
        self.loading = False
        await self.stream.write(fragment)
        self.scroll_end()
