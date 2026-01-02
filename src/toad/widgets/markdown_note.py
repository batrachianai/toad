from typing import Iterable
from textual.widgets import Markdown

from toad.menus import MenuItem
from toad.rtl import apply_bidi_to_markdown


class MarkdownNote(Markdown):
    def __init__(
        self,
        markdown: str | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        parser_factory: type | None = None,
    ) -> None:
        # Apply RTL support for Hebrew, Arabic, and other BiDi languages
        if markdown is not None:
            markdown = apply_bidi_to_markdown(markdown)
        super().__init__(
            markdown,
            name=name,
            id=id,
            classes=classes,
            parser_factory=parser_factory,
        )

    def get_block_menu(self) -> Iterable[MenuItem]:
        return
        yield

    def get_block_content(self, destination: str) -> str | None:
        return self.source
