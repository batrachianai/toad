from textual import on
from textual.app import ComposeResult
from textual import containers

from textual import getters
from textual.binding import Binding
from textual.screen import Screen
from textual.reactive import var, Initialize


from toad.answer import Answer
from toad.widgets.question import Question
from toad.widgets.diff_view import DiffView

from textual.widgets import OptionList, Footer, Static, Select
from textual.widgets.option_list import Option

from toad.app import ToadApp

SOURCE1 = '''\
def loop_first(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for first value."""
    iter_values = iter(values)
    try:
        value = next(iter_values)
    except StopIteration:
        return
    yield True, value
    for value in iter_values:
        yield False, value


def loop_first_last(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for first and last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)
    except StopIteration:
        return
    first = True
    for value in iter_values:
        yield first, False, previous_value
        first = False
        previous_value = value
    yield first, True, previous_value

'''

SOURCE2 = '''\
def loop_first(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for first value.
    
    Args:
        values: iterables of values.

    Returns:
        Iterable of a boolean to indicate first value, and a value from the iterable.
    """
    iter_values = iter(values)
    try:
        value = next(iter_values)
    except StopIteration:
        return
    yield True, value
    for value in iter_values:
        yield False, value


def loop_last(values: Iterable[T]) -> Iterable[tuple[bool, bool, T]]:
    """Iterate and generate a tuple with a flag for last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)
    except StopIteration:
        return
    for value in iter_values:
        yield False, previous_value
        previous_value = value
    yield True, previous_value


def loop_first_last(values: Iterable[ValueType]) -> Iterable[tuple[bool, bool, ValueType]]:
    """Iterate and generate a tuple with a flag for first and last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)  # Get previous value
    except StopIteration:
        return
    first = True

'''


class PermissionsQuestion(Question):
    BINDING_GROUP_TITLE = "Permissions Options"


class ChangesOptionList(OptionList):
    BINDING_GROUP_TITLE = "Changes list"


class DiffViewSelect(Select):
    BINDING_GROUP_TITLE = "Diff view select"


class ToolScroll(containers.VerticalScroll):
    BINDING_GROUP_TITLE = "Changes window"


class PermissionsScreen(Screen[str]):
    BINDING_GROUP_TITLE = "Permissions"
    AUTO_FOCUS = "Question"
    CSS_PATH = "permissions.tcss"

    TAB_GROUP = Binding.Group("Focus")
    NAVIGATION_GROUP = Binding.Group("Navigation", compact=True)
    BINDINGS = [
        Binding("j", "next", "Next", group=NAVIGATION_GROUP),
        Binding("k", "previous", "Previous", group=NAVIGATION_GROUP),
        Binding(
            "tab",
            "app.focus_next",
            "Focus next",
            group=TAB_GROUP,
            show=True,
            priority=True,
        ),
        Binding(
            "shift+tab",
            "app.focus_previous",
            "Focus previous",
            group=TAB_GROUP,
            show=True,
            priority=True,
        ),
    ]

    tool_container = getters.query_one("#tool-container", containers.VerticalScroll)
    navigator = getters.query_one("#navigator", OptionList)
    index: var[int] = var(0)

    def get_diff_type(self) -> str:
        app = self.app
        diff_type = "auto"
        if isinstance(app, ToadApp):
            diff_type = app.settings.get("diff.view", str)
        return diff_type

    diff_type: var[str] = var(Initialize(get_diff_type))

    def compose(self) -> ComposeResult:
        with containers.Grid(classes="top"):
            yield DiffViewSelect(
                [
                    ("Unified diff", "unified"),
                    ("Split diff", "split"),
                    ("Auto diff", "auto"),
                ],
                value=self.diff_type,
                allow_blank=False,
                id="diff-select",
            )
            yield Static(
                "[b]Approval request[/b] [dim]The Agent wishes to make the following changes",
                id="instructions",
            )
            with containers.Vertical(id="nav-container"):
                yield PermissionsQuestion(
                    "",
                    options=[
                        Answer("Allow once", "allow_once", kind="allow_once"),
                        Answer("Allow always", "allow_always", kind="allow_always"),
                        Answer("Reject once", "reject_once", kind="reject_once"),
                        Answer("Reject always", "reject_always", kind="reject_always"),
                    ],
                )
                yield ChangesOptionList(id="navigator")
            yield ToolScroll(id="tool-container")

        yield Footer()

    async def on_mount(self):
        app = self.app
        if isinstance(app, ToadApp):
            diff_view_setting = app.settings.get("diff.view", str)
            self.query_one("#diff-select", Select).value = diff_view_setting

        await self.add_diff("foo.py", "foo.py", SOURCE1, SOURCE2)
        self.navigator.highlighted = 0

    async def add_diff(
        self, path1: str, path2: str, before: str | None, after: str
    ) -> None:
        self.index += 1
        option_id = f"item-{self.index}"
        diff_view = DiffView(path1, path2, before or "", after, id=option_id)
        await diff_view.prepare()
        app = self.app
        if isinstance(app, ToadApp):
            diff_view_setting = app.settings.get("diff.view", str)
            diff_view.split = diff_view_setting == "split"
            diff_view.auto_split = diff_view_setting == "auto"
        await self.tool_container.mount(diff_view)
        option_text = f"📄 {path1}"
        self.navigator.add_option(Option(option_text, option_id))

    @on(OptionList.OptionHighlighted)
    def on_option_highlighted(self, event: OptionList.OptionHighlighted):
        self.tool_container.query_one(f"#{event.option_id}").scroll_visible(top=True)

    @on(Question.Answer)
    def on_question_answer(self, event: Question.Answer) -> None:
        def dismiss():
            self.dismiss(event.answer.id)

        self.set_timer(0.4, dismiss)

    @on(Select.Changed, "#diff-select")
    def on_diff_select(self, event: Select.Changed) -> None:
        diff_type = event.value
        for diff_view in self.query(DiffView):
            diff_view.auto_split = diff_type == "auto"
            diff_view.split = diff_type == "split"

    def action_next(self) -> None:
        self.navigator.action_cursor_down()

    def action_previous(self) -> None:
        self.navigator.action_cursor_up()


if __name__ == "__main__":
    SOURCE1 = '''\
def loop_first(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for first value."""
    iter_values = iter(values)
    try:
        value = next(iter_values)
    except StopIteration:
        return
    yield True, value
    for value in iter_values:
        yield False, value


def loop_first_last(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for first and last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)
    except StopIteration:
        return
    first = True
    for value in iter_values:
        yield first, False, previous_value
        first = False
        previous_value = value
    yield first, True, previous_value

'''

    SOURCE2 = '''\
def loop_first(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for first value.
    
    Args:
        values: iterables of values.

    Returns:
        Iterable of a boolean to indicate first value, and a value from the iterable.
    """
    iter_values = iter(values)
    try:
        value = next(iter_values)
    except StopIteration:
        return
    yield True, value
    for value in iter_values:
        yield False, value


def loop_last(values: Iterable[T]) -> Iterable[tuple[bool, bool, T]]:
    """Iterate and generate a tuple with a flag for last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)
    except StopIteration:
        return
    for value in iter_values:
        yield False, previous_value
        previous_value = value
    yield True, previous_value


def loop_first_last(values: Iterable[ValueType]) -> Iterable[tuple[bool, bool, ValueType]]:
    """Iterate and generate a tuple with a flag for first and last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)  # Get previous value
    except StopIteration:
        return
    first = True

'''

    from textual.app import App

    class PermissionTestApp(App):
        async def on_mount(self) -> None:
            screen = PermissionsScreen()
            await self.push_screen(screen)
            # for repeat in range(5):
            #     await screen.add_diff("foo.py", "foo.py", SOURCE1, SOURCE2)

    app = PermissionTestApp()
    app.run()
