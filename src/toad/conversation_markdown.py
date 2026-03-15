from typing import Iterable

from textual.widgets import Markdown
from textual.widgets._markdown import MarkdownBlock


from toad.menus import MenuItem


class ConversationCodeFence(Markdown.BLOCKS["fence"]):

    def get_block_menu(self) -> Iterable[MenuItem]:
        yield from ()

    def get_block_content(self, destination: str) -> str | None:
        if destination == "clipboard":
            return self._content.plain
        return self.source


CUSTOM_BLOCKS = {"fence": ConversationCodeFence}


class ConversationMarkdown(Markdown):
    """Markdown widget with custom blocks."""

    def get_block_class(self, block_name: str) -> type[MarkdownBlock]:
        if (custom_block := CUSTOM_BLOCKS.get(block_name)) is not None:
            return custom_block
        return super().get_block_class(block_name)
