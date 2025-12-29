from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from textual.app import ComposeResult
from textual import events, on
from textual.binding import Binding
from textual import containers
from textual.content import Content
from textual.reactive import var, reactive
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label

from toad.answer import Answer

type Options = list[Answer]


@dataclass
class Ask:
    """Data for Question."""

    question: str
    options: Options
    callback: Callable[[Answer], Any] | None = None


class NonSelectableLabel(Label):
    ALLOW_SELECT = False


class Option(containers.HorizontalGroup):
    ALLOW_SELECT = False
    DEFAULT_CSS = """
    Option {

        &:hover {
            background: $boost;
        }
        color: $text-muted;
        #caret {
            visibility: hidden;
            padding: 0 1;
        }
        #index {
            padding-right: 1;
        }
        #label {
            width: 1fr;
        }
        &.-active {            
            color: $text-accent;
            #caret {
                visibility: visible;
            }
        }
        &.-selected {
            opacity: 0.5;
        }
        &.-active.-selected {
            opacity: 1.0;
            background: transparent;
            color: $text-accent;            
            #label {
                text-style: underline;
            }
            #caret {
                visibility: hidden;
            }
        }
    }
    """

    @dataclass
    class Selected(Message):
        """The option was selected."""

        index: int

    selected: reactive[bool] = reactive(False, toggle_class="-selected")

    def __init__(
        self, index: int, content: Content, key: str | None, classes: str = ""
    ) -> None:
        super().__init__(classes=classes)
        self.index = index
        self.content = content
        self.key = key

    def compose(self) -> ComposeResult:
        key = self.key
        yield NonSelectableLabel("❯", id="caret")
        if key:
            yield NonSelectableLabel(Content.styled(f"{key}", "b"), id="index")
        else:
            yield NonSelectableLabel(Content(" "), id="index")

        yield NonSelectableLabel(self.content, id="label")

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Selected(self.index))


class Question(Widget, can_focus=True):
    """A text question with a menu of responses."""

    BINDING_GROUP_TITLE = "Question"
    ALLOW_SELECT = False
    CURSOR_GROUP = Binding.Group("Cursor", compact=True)
    ALLOW_GROUP = Binding.Group("Allow once/always", compact=True)
    REJECT_GROUP = Binding.Group("Reject once/always", compact=True)
    BINDINGS = [
        Binding(
            "up",
            "selection_up",
            "Up",
            group=CURSOR_GROUP,
        ),
        Binding(
            "down",
            "selection_down",
            "Down",
            group=CURSOR_GROUP,
        ),
        Binding(
            "enter",
            "select",
            "Select",
        ),
        Binding(
            "a",
            "select_kind(('allow_once', 'allow'))",
            "Allow once",
            group=ALLOW_GROUP,
        ),
        Binding(
            "A",
            "select_kind('allow_always')",
            "Allow always",
            group=ALLOW_GROUP,
        ),
        Binding(
            "r",
            "select_kind(('reject_once', 'reject'))",
            "Reject once",
            group=REJECT_GROUP,
        ),
        Binding(
            "R",
            "select_kind('reject_always')",
            "Reject always",
            group=REJECT_GROUP,
        ),
    ]

    DEFAULT_CSS = """
    Question {
        width: 1fr;
        height: auto;
        padding: 0 1; 
        background: transparent;
        #prompt {
            margin-bottom: 1;
            color: $text-primary;
        }                
        &.-blink Option.-active #caret {
            opacity: 0.2;
        }
        &:blur {
            #index {
                opacity: 0.3;
            }
            #caret {
                opacity: 0.3;
            }
        }
    }
    """

    question: var[str] = var("")
    options: var[Options] = var(list)

    selection: reactive[int] = reactive(0, init=False)
    selected: var[bool] = var(False, toggle_class="-selected")
    blink: var[bool] = var(False)

    DEFAULT_KINDS = {
        "allow_once": "a",
        "allow_always": "A",
        "reject_once": "r",
        "reject_always": "R",
    }

    @dataclass
    class Answer(Message):
        """User selected a response."""

        index: int
        answer: Answer

    def __init__(
        self,
        question: str = "Ask and you will receive",
        options: Options | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.set_reactive(Question.question, question)
        self.set_reactive(Question.options, options or [])

    def on_mount(self) -> None:
        def toggle_blink() -> None:
            if self.has_focus:
                self.blink = not self.blink
            else:
                self.blink = False

        self._blink_timer = self.set_interval(0.5, toggle_blink)

    def _reset_blink(self) -> None:
        self.blink = False
        self._blink_timer.reset()

    def update(self, ask: Ask) -> None:
        self.question = ask.question
        self.options = ask.options
        self.selection = 0
        self.selected = False
        self.refresh(recompose=True, layout=True)

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup():
            if self.question:
                yield Label(self.question, id="prompt")

            with containers.VerticalGroup(id="option-container"):
                kinds: set[str] = set()
                for index, answer in enumerate(self.options):
                    active = index == self.selection
                    key = (
                        self.DEFAULT_KINDS.get(answer.kind)
                        if (answer.kind and answer.kind not in kinds)
                        else None
                    )
                    yield Option(
                        index,
                        Content(answer.text),
                        key,
                        classes="-active" if active else "",
                    ).data_bind(Question.selected)
                    if answer.kind is not None:
                        kinds.add(answer.kind)

    def watch_selection(self, old_selection: int, new_selection: int) -> None:
        self.query("#option-container > .-active").remove_class("-active")
        if new_selection >= 0:
            self.query_one("#option-container").children[new_selection].add_class(
                "-active"
            )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.selected and action in ("selection_up", "selection_down"):
            return False
        if action == "select_kind":
            kinds = {answer.kind for answer in self.options if answer.kind is not None}
            check_kinds = set()
            for parameter in parameters:
                if isinstance(parameter, str):
                    check_kinds.add(parameter)
                elif isinstance(parameter, tuple):
                    check_kinds.update(parameter)

            return any(kind in kinds for kind in check_kinds)

        return True

    def watch_blink(self, blink: bool) -> None:
        self.set_class(blink, "-blink")

    def action_selection_up(self) -> None:
        self._reset_blink()
        self.selection = max(0, self.selection - 1)

    def action_selection_down(self) -> None:
        self._reset_blink()
        self.selection = min(len(self.options) - 1, self.selection + 1)

    def action_select(self) -> None:
        self._reset_blink()
        self.post_message(
            self.Answer(
                index=self.selection,
                answer=self.options[self.selection],
            )
        )
        self.selected = True

    def action_select_kind(self, kind: str | tuple[str]) -> None:
        kinds = kind if isinstance(kind, tuple) else (kind,)
        for kind in kinds:
            for index, answer in enumerate(self.options):
                if answer.kind == kind:
                    self.selection = index
                    self.action_select()
                    break

    @on(Option.Selected)
    def on_option_selected(self, event: Option.Selected) -> None:
        event.stop()
        self._reset_blink()
        if not self.selected:
            self.selection = event.index


if __name__ == "__main__":
    from textual.app import App
    from textual.widgets import Footer

    OPTIONS = [
        Answer("Yes, allow once", "proceed_always", kind="allow_once"),
        Answer("Yes, allow always", "allow_always", kind="allow_always"),
        Answer("Modify with external editor", "modify", kind="allow_once"),
        Answer("No, suggest changes (esc)", "reject"),
    ]

    class QuestionApp(App):
        def compose(self) -> ComposeResult:
            yield Question("Apply this change?", OPTIONS)
            yield Footer()

    QuestionApp().run()
