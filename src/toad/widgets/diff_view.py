from __future__ import annotations

from itertools import zip_longest

from textual.app import ComposeResult
from textual.content import Content
from textual.geometry import Size
from textual import highlight
from textual._segment_tools import line_pad
from textual.css.styles import RulesMap
from textual.strip import Strip
from textual.style import Style
from textual.reactive import reactive
from textual.visual import Visual, RenderOptions
from textual.widget import Widget
from textual.widgets import Static
from textual import containers

import difflib


class LineContent(Visual):
    def __init__(self, lines_and_colors: list[tuple[Content, str]]) -> None:
        self.lines_and_colors = lines_and_colors

    def render_strips(
        self, width: int, height: int | None, style: Style, options: RenderOptions
    ) -> list[Strip]:
        strips: list[Strip] = []
        for line, color in self.lines_and_colors:
            if line.cell_length < width:
                line = line.extend_right(width - line.cell_length)
            line = line.stylize_before(color).stylize_before(style)

            # TODO: rich_style_with_offsets needed to make content selectable
            strips.append(Strip(line.render_segments(), line.cell_length))
        return strips

    def get_optimal_width(self, rules: RulesMap, container_width: int) -> int:
        return max(line.cell_length for line, color in self.lines_and_colors)

    def get_minimal_width(self, rules: RulesMap) -> int:
        return 1

    def get_height(self, rules: RulesMap, width: int) -> int:
        return len(self.lines_and_colors)


class LineNumbers(Widget):
    DEFAULT_CSS = """
    LineNumbers {
        width: auto;
        height: auto;                
    }
    """
    numbers: reactive[list[Content]] = reactive(list)
    left_pad: reactive[int] = reactive(1)
    right_pad: reactive[int] = reactive(1)

    def __init__(
        self,
        numbers: list[Content],
        *,
        left_pad=0,
        right_pad=0,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        self.set_reactive(LineNumbers.left_pad, left_pad)
        self.set_reactive(LineNumbers.right_pad, right_pad)
        self.numbers = numbers

    @property
    def total_width(self) -> int:
        return self.left_pad + self.number_width + self.right_pad

    def get_content_width(self, container: Size, viewport: Size) -> int:
        return self.total_width

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return len(self.numbers)

    @property
    def number_width(self) -> int:
        numbers = self.numbers
        if numbers:
            return max(number.cell_length for number in numbers)
        else:
            return 0

    def render_line(self, y: int) -> Strip:
        width = self.total_width
        visual_style = self.visual_style
        rich_style = visual_style.rich_style
        try:
            number = self.numbers[y]
        except IndexError:
            number = Content.empty()

        strip = Strip(
            line_pad(
                number.render_segments(visual_style),
                self.left_pad,
                self.right_pad,
                rich_style,
            ),
            cell_length=number.cell_length + self.left_pad + self.right_pad,
        )
        strip = strip.adjust_cell_length(width, rich_style)
        return strip


class DiffCode(Static):
    DEFAULT_CSS = """
    DiffCode {
        width: auto;        
        height: auto;
        min-width: 1fr;
    }
    """


class DiffView(containers.HorizontalGroup):
    code_before: reactive[str] = reactive("")
    code_after: reactive[str] = reactive("")
    path1: reactive[str] = reactive("")
    path2: reactive[str] = reactive("")
    language: reactive[str | None] = reactive(None)

    DEFAULT_CSS = """
    DiffView {
        width: 1fr;
        height: auto;
    }
    """

    def __init__(
        self,
        path1: str,
        path2: str,
        code_before: str,
        code_after: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.set_reactive(DiffView.path1, path1)
        self.set_reactive(DiffView.path2, path2)
        self.set_reactive(DiffView.code_before, code_before)
        self.set_reactive(DiffView.code_after, code_after)

    def compose(self) -> ComposeResult:
        language1 = highlight.guess_language(self.code_before, self.path1)
        language2 = highlight.guess_language(self.code_after, self.path2)

        text_lines_a = self.code_before.splitlines()
        text_lines_b = self.code_after.splitlines()

        lines_a = highlight.highlight(
            "\n".join(text_lines_a), language=language1, path=self.path1
        ).split("\n")
        lines_b = highlight.highlight(
            "\n".join(text_lines_b), language=language2, path=self.path2
        ).split("\n")

        output_lines: list[tuple[Content, str]] = []
        line_numbers: list[tuple[str, int]] = []

        for group in difflib.SequenceMatcher(
            None, text_lines_a, text_lines_b
        ).get_grouped_opcodes():
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for line_number, line in enumerate(lines_a[i1:i2], i1 + 1):
                        output_lines.append((line, ""))
                        line_numbers.append(("", line_number))
                    continue
                if tag in {"replace", "delete"}:
                    for line_number, line in enumerate(lines_a[i1:i2], i1 + 1):
                        output_lines.append((line, "on $error 15%"))
                        line_numbers.append(("-", line_number))
                if tag in {"replace", "insert"}:
                    for line_number, line in enumerate(lines_b[j1:j2], j1 + 1):
                        output_lines.append((line, "on $success 15%"))
                        line_numbers.append(("+", line_number))

        if line_numbers:
            line_number_width = max(
                len(str(line_number)) for _, line_number in line_numbers
            )
        else:
            line_number_width = 0
        annotations = {
            "+": Content.styled(" + ", "bold on $success 15%"),
            "-": Content.styled(" - ", "bold on $error 15%"),
            "": Content("   "),
        }
        annotation_style = {
            "+": "$foreground 90% on $success 30%",
            "-": "$foreground 90% on $error 30%",
            "": "$foreground 30%",
        }
        line_number_display = [
            Content.assemble(
                Content.styled(f" {line_number:>{line_number_width}} ", "").stylize(
                    annotation_style[annotation]
                ),
                annotations[annotation],
            )
            for (annotation, line_number) in line_numbers
        ]

        print(line_numbers)
        yield LineNumbers(line_number_display)
        yield DiffCode(LineContent(output_lines))


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


def loop_first_last(values: Iterable[T]) -> Iterable[tuple[bool, bool, T]]:
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


def loop_last(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
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
    from textual.app import App

    class DiffApp(App):
        def compose(self) -> ComposeResult:
            yield DiffView("foo.py", "foo.py", SOURCE1, SOURCE2)

    app = DiffApp()
    app.run()
