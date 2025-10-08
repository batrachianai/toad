from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.reactive import var, reactive
from textual import getters
from textual.widgets import Footer, OptionList, DirectoryTree
from textual import containers


from toad.widgets.throbber import Throbber
from toad.widgets.conversation import Conversation
from toad.widgets.explain import Explain
from toad.widgets.version import Version


class MainScreen(Screen, can_focus=False):
    AUTO_FOCUS = "Conversation Prompt TextArea"

    BINDINGS = [
        Binding("f3", "show_files", "Files"),
        Binding("f3", "hide_files", "Hide files"),
    ]

    BINDING_GROUP_TITLE = "Screen"
    busy_count = var(0)
    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    conversation = getters.query_one(Conversation)
    directory_tree = getters.query_one(DirectoryTree)

    column = reactive(False)
    column_width = reactive(100)
    scrollbar = reactive("")
    show_tree = reactive(False, toggle_class="-show-tree", bindings=True)
    project_path: var[Path] = var(Path("./").expanduser().absolute())

    def compose(self) -> ComposeResult:
        yield Version("Toad v0.1")

        with containers.Center():
            yield DirectoryTree("./")
            yield Explain()
            yield Conversation(self.project_path).data_bind(MainScreen.project_path)
        yield Footer()

    def on_mount(self) -> None:
        # self.directory_tree.show_guides = False
        self.directory_tree.guide_depth = 3

    @on(OptionList.OptionHighlighted)
    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if event.option.id is not None:
            self.conversation.prompt.suggest(event.option.id)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "show_files" and self.show_tree:
            return False
        if action == "hide_files" and not self.show_tree:
            return False
        return True

    def action_show_files(self) -> None:
        self.show_tree = True

    def action_hide_files(self) -> None:
        self.show_tree = False
        self.conversation.prompt.focus()

    def action_focus_prompt(self) -> None:
        self.conversation.focus_prompt()

    def watch_column(self, column: bool) -> None:
        self.set_class(column, "-column")
        self.conversation.styles.max_width = (
            max(10, self.column_width) if column else None
        )

    def watch_column_width(self, column_width: int) -> None:
        self.conversation.styles.max_width = (
            max(10, column_width) if self.column else None
        )

    def watch_scrollbar(self, old_scrollbar: str, scrollbar: str) -> None:
        if old_scrollbar:
            self.conversation.remove_class(f"-scrollbar-{old_scrollbar}")
        self.conversation.add_class(f"-scrollbar-{scrollbar}")
