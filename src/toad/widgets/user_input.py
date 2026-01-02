from typing import Iterable
from textual.app import ComposeResult
from textual import containers
from textual.widgets import Markdown

from toad.menus import MenuItem
from toad.widgets.non_selectable_label import NonSelectableLabel
from toad.rtl import apply_bidi_to_markdown


class UserInput(containers.HorizontalGroup):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        yield NonSelectableLabel("❯", id="prompt")
        # Apply RTL support for Hebrew, Arabic, and other BiDi languages
        yield Markdown(apply_bidi_to_markdown(self.content), id="content")

    def get_block_menu(self) -> Iterable[MenuItem]:
        yield from ()

    def get_block_content(self, destination: str) -> str | None:
        return self.content
