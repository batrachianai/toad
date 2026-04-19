import os
from textual import work, on
from textual.app import ComposeResult
from textual import containers

from textual import getters
from textual.binding import Binding
from textual.content import Content
from textual.screen import Screen
from textual.reactive import var, Initialize

from textual.widgets import OptionList, Footer, Static, Select
from textual.widgets.option_list import Option

from toad.answer import Answer
from toad.widgets.question import Question

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


class PermissionsScreen(Screen[Answer]):
    BINDING_GROUP_TITLE = "Permissions"
    AUTO_FOCUS = "Question"
    CSS_PATH = "permissions.tcss"

    TAB_GROUP = Binding.Group("Focus")
    NAVIGATION_GROUP = Binding.Group("Navigation", compact=True)
    ALLOW_GROUP = Binding.Group("Allow once/always", compact=True)
    REJECT_GROUP = Binding.Group("Reject once/always", compact=True)
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
        Binding(
            "a",
            "select_kind(('allow_once', 'allow'))",
            "Allow once",
            group=ALLOW_GROUP,
            priority=True,
        ),
        Binding(
            "A",
            "select_kind('allow_always')",
            "Allow always",
            group=ALLOW_GROUP,
            priority=True,
        ),
        Binding(
            "r",
            "select_kind(('reject_once', 'reject'))",
            "Reject once",
            group=REJECT_GROUP,
            priority=True,
        ),
        Binding(
            "R",
            "select_kind('reject_always')",
            "Reject always",
            group=REJECT_GROUP,
            priority=True,
        ),
    ]

    tool_container = getters.query_one("#tool-container", containers.VerticalScroll)
    navigator = getters.query_one("#navigator", OptionList)
    question = getters.query_one(PermissionsQuestion)
    index: var[int] = var(0)

    def __init__(
        self,
        options: list[Answer],
        diffs: list[tuple[str, str, str | None, str]] | None = None,
        agent_name: str = "The Agent",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """

        Args:
            options: Potential answers to the permission request.
            diffs: List of diffs to display, tuples of (PATH1, PATH2, SOURCE1, SOURCE2)
            name: Textual name attribute.
            id: Textual id attribute.
            classe: Textual classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.options = options
        self.diffs = diffs
        self.agent_name = agent_name

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
                Content.from_markup(
                    "[b]Approval request[/b] [dim]$name wishes to make the following changes",
                    name=self.agent_name,
                ),
                id="instructions",
            )
            with containers.Vertical(id="nav-container"):
                yield PermissionsQuestion("", options=self.options)
                yield ChangesOptionList(id="navigator")
            yield ToolScroll(id="tool-container")

        yield Footer()

    def action_select_kind(self, kind: str | tuple[str]) -> None:
        self.question.action_select_kind(kind)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "select_kind":
            kinds = {
                answer.kind
                for answer in self.question.options
                if answer.kind is not None
            }
            check_kinds = set()
            for parameter in parameters:
                if isinstance(parameter, str):
                    check_kinds.add(parameter)
                elif isinstance(parameter, tuple):
                    check_kinds.update(parameter)

            return any(kind in kinds for kind in check_kinds)

        return True

    async def on_mount(self):
        app = self.app
        if isinstance(app, ToadApp):
            diff_view_setting = app.settings.get("diff.view", str)
            self.query_one("#diff-select", Select).value = diff_view_setting
        self.navigator.highlighted = 0

        self._add_diffs()
        self.question.focus()

    @work
    async def _add_diffs(self) -> None:
        """Add any diffs given in the constructor."""
        if self.diffs is None:
            return
        diffs = self.diffs[:]
        self.diffs = None
        for diff in diffs:
            await self.add_diff(*diff)

    async def add_diff(
        self, path1: str, path2: str, before: str | None, after: str
    ) -> None:
        self.index += 1
        option_id = f"item-{self.index}"
        from toad.widgets.diff_view import make_diff

        diff_view = make_diff(path1, path2, before, after, id=option_id)
        await diff_view.prepare()

        await self.tool_container.mount(diff_view)

        option_text = f"📄 {os.path.basename(path1)}"
        self.navigator.add_option(Option(option_text, option_id))

    @on(OptionList.OptionHighlighted)
    def on_option_highlighted(self, event: OptionList.OptionHighlighted):
        self.tool_container.query_one(f"#{event.option_id}").scroll_visible(top=True)

    @on(Question.Answer)
    def on_question_answer(self, event: Question.Answer) -> None:
        def dismiss():
            self.dismiss(event.answer)

        self.set_timer(0.4, dismiss)

    @on(Select.Changed, "#diff-select")
    def on_diff_select(self, event: Select.Changed) -> None:
        diff_type = event.value
        from textual_diff_view import DiffView

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
    from textual import work
    from textual.app import App

    class PermissionTestApp(App):
        @work
        async def on_mount(self) -> None:
            screen = PermissionsScreen(
                [Answer("Foo", "allow_once", kind="allow_once"), Answer("Bar", "bar")],
                [("foo.py", "foo2.py", SOURCE1, SOURCE2)],
            )
            result = await self.push_screen_wait(screen)
            self.notify(str(result))
            # for repeat in range(5):
            #     await screen.add_diff("foo.py", "foo.py", SOURCE1, SOURCE2)

    app = PermissionTestApp()
    app.run()
