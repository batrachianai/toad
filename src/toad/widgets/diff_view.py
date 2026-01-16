from __future__ import annotations


import asyncio
import difflib
from itertools import starmap
from typing import Iterable, Literal

from rich.segment import Segment
from rich.style import Style as RichStyle

from textual.app import ComposeResult
from textual.content import Content, Span
from textual.geometry import Size
from textual import highlight
from textual import events

from textual.css.styles import RulesMap
from textual.selection import Selection
from textual.strip import Strip
from textual.style import Style
from textual.reactive import reactive, var
from textual.visual import Visual, RenderOptions
from textual.widget import Widget
from textual.widgets import Static
from textual import containers

type Annotation = Literal["+", "-", "/", " "]


class DiffScrollContainer(containers.HorizontalGroup):
    scroll_link: var[Widget | None] = var(None)
    DEFAULT_CSS = """
    DiffScrollContainer {
        overflow: scroll hidden;
        scrollbar-size: 0 0;
        height: auto;
    }
    """

    def watch_scroll_x(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_x(old_value, new_value)
        if self.scroll_link:
            self.scroll_link.scroll_x = new_value


class LineContent(Visual):
    def __init__(
        self,
        code_lines: list[Content | None],
        line_styles: list[str],
        width: int | None = None,
    ) -> None:
        self.code_lines = code_lines
        self.line_styles = line_styles
        self._width = width

    def render_strips(
        self, width: int, height: int | None, style: Style, options: RenderOptions
    ) -> list[Strip]:
        strips: list[Strip] = []
        y = 0
        selection = options.selection
        selection_style = options.selection_style or Style.null()
        for y, (line, color) in enumerate(zip(self.code_lines, self.line_styles)):
            if line is None:
                line = Content.styled("╲" * width, "$foreground 15%")
            else:
                if selection is not None:
                    if span := selection.get_span(y):
                        start, end = span
                        if end == -1:
                            end = len(line)
                        line = line.stylize(selection_style, start, end)
                if line.cell_length < width:
                    line = line.pad_right(width - line.cell_length)

            line = line.stylize_before(color).stylize_before(style)
            x = 0
            meta = {"offset": (x, y)}
            segments = []
            for text, rich_style, _ in line.render_segments():
                if rich_style is not None:
                    meta["offset"] = (x, y)
                    segments.append(
                        Segment(text, rich_style + RichStyle.from_meta(meta))
                    )
                else:
                    segments.append(Segment(text, rich_style))
                x += len(text)

            strips.append(Strip(segments, line.cell_length))
        return strips

    def get_optimal_width(self, rules: RulesMap, container_width: int) -> int:
        if self._width is not None:
            return self._width
        return max(line.cell_length for line in self.code_lines if line is not None)

    def get_minimal_width(self, rules: RulesMap) -> int:
        return 1

    def get_height(self, rules: RulesMap, width: int) -> int:
        return len(self.line_styles)


class LineAnnotations(Widget):
    """A vertical strip next to the code, containing line numbers or symbols."""

    DEFAULT_CSS = """
    LineAnnotations {
        width: auto;
        height: auto;                
    }
    """
    numbers: reactive[list[Content]] = reactive(list)

    def __init__(
        self,
        numbers: Iterable[Content],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.numbers = list(numbers)

    @property
    def total_width(self) -> int:
        return self.number_width

    def get_content_width(self, container: Size, viewport: Size) -> int:
        return self.total_width

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return len(self.numbers)

    @property
    def number_width(self) -> int:
        return max(number.cell_length for number in self.numbers) if self.numbers else 0

    def render_line(self, y: int) -> Strip:
        width = self.total_width
        visual_style = self.visual_style
        rich_style = visual_style.rich_style
        try:
            number = self.numbers[y]
        except IndexError:
            number = Content.empty()

        strip = Strip(
            number.render_segments(visual_style), cell_length=number.cell_length
        )
        strip = strip.adjust_cell_length(width, rich_style)
        return strip


class DiffCode(Static):
    """Container for the code."""

    DEFAULT_CSS = """
    DiffCode {
        width: auto;        
        height: auto;
        min-width: 1fr;
    }
    """
    ALLOW_SELECT = True

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        visual = self._render()
        if isinstance(visual, LineContent):
            text = "\n".join(
                "" if line is None else line.plain for line in visual.code_lines
            )
        else:
            return None
        return selection.extract(text), "\n"


def fill_lists[T](list_a: list[T], list_b: list[T], fill_value: T) -> None:
    """Make two lists the same size by extending the smaller with a fill value.

    Args:
        list_a: The first list.
        list_b: The second list.
        fill_value: Value used to extend a list.

    """
    a_length = len(list_a)
    b_length = len(list_b)
    if a_length != b_length:
        if a_length > b_length:
            list_b.extend([fill_value] * (a_length - b_length))
        elif b_length > a_length:
            list_a.extend([fill_value] * (b_length - a_length))


class DiffView(containers.VerticalGroup):
    """A formatted diff in unified or split format."""

    code_before: reactive[str] = reactive("")
    code_after: reactive[str] = reactive("")
    path1: reactive[str] = reactive("")
    path2: reactive[str] = reactive("")
    split: reactive[bool] = reactive(True, recompose=True)
    annotations: var[bool] = var(False, toggle_class="-with-annotations")
    auto_split: var[bool] = var(False)

    DEFAULT_CSS = """
    DiffView {
        width: 1fr;
        height: auto;
        
        .diff-group {
            height: auto;
            background: $foreground 4%;
            margin-bottom: 1;
        }                

        .annotations { width: 1; }
        &.-with-annotations {
            .annotations { width: auto; }
        }
        .title {            
            border-bottom: dashed $foreground 20%;
        }
        
    }
    """

    NUMBER_STYLES = {
        "+": "$text-success 80% on $success 20%",
        "-": "$text-error 80% on $error 20%",
        " ": "$foreground 30% on $foreground 3%",
    }
    LINE_STYLES = {
        "+": "on $success 10%",
        "-": "on $error 10%",
        " ": "",
        "/": "",
    }

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
        self.set_reactive(DiffView.code_before, code_before.expandtabs())
        self.set_reactive(DiffView.code_after, code_after.expandtabs())
        self._grouped_opcodes: list[list[tuple[str, int, int, int, int]]] | None = None
        self._highlighted_code_lines: tuple[list[Content], list[Content]] | None = None

    async def prepare(self) -> None:
        """Do CPU work in a thread.

        Call this method prior to composing or mounting to ensure lazy calculated
        data structures run in a thread. Otherwise the work will be done in the async
        loop, potentially causing a brief freeze.

        """

        def prepare() -> None:
            """Call properties which will lazily update data structures."""
            self.grouped_opcodes
            self.highlighted_code_lines

        await asyncio.to_thread(prepare)

    @property
    def grouped_opcodes(self) -> list[list[tuple[str, int, int, int, int]]]:
        if self._grouped_opcodes is None:
            text_lines_a = self.code_before.splitlines()
            text_lines_b = self.code_after.splitlines()
            sequence_matcher = difflib.SequenceMatcher(
                lambda character: character in " \t",
                text_lines_a,
                text_lines_b,
                autojunk=True,
            )
            self._grouped_opcodes = list(sequence_matcher.get_grouped_opcodes())

        return self._grouped_opcodes

    @property
    def counts(self) -> tuple[int, int]:
        """Additions and removals."""
        additions = 0
        removals = 0
        for group in self.grouped_opcodes:
            for tag, i1, i2, j1, j2 in group:
                if tag == "delete":
                    removals += 1
                elif tag == "replace":
                    additions += 1
                    removals += 1
                elif tag == "insert":
                    additions += 1
        return additions, removals

    @classmethod
    def _highlight_diff_lines(
        cls, lines_a: list[Content], lines_b: list[Content]
    ) -> tuple[list[Content], list[Content]]:
        """Diff two groups of lines.

        Args:
            lines_a: Lines before.
            lines_b: Lines after

        Returns:
            A pair of highlighted lists of lines.
        """
        code_a = Content("\n").join(content for content in lines_a)
        code_b = Content("\n").join(content for content in lines_b)
        sequence_matcher = difflib.SequenceMatcher(
            lambda character: character in " \t",
            code_a.plain,
            code_b.plain,
            autojunk=True,
        )
        spans_a: list[Span] = []
        spans_b: list[Span] = []
        for tag, i1, i2, j1, j2 in sequence_matcher.get_opcodes():
            if tag in {"delete", "replace"}:
                spans_a.append(Span(i1, i2, "on $error 40%"))
            if tag in {"insert", "replace"}:
                spans_b.append(Span(j1, j2, "on $success 40%"))
        diffed_lines_a = code_a.add_spans(spans_a).split("\n")
        diffed_lines_b = code_b.add_spans(spans_b).split("\n")
        return diffed_lines_a, diffed_lines_b

    @property
    def highlighted_code_lines(self) -> tuple[list[Content], list[Content]]:
        """Get syntax highlighted code for both files, as a list of lines.

        Returns:
            A pair of line lists for `code_before` and `code_after`
        """

        if self._highlighted_code_lines is None:
            language1 = highlight.guess_language(self.code_before, self.path1)
            language2 = highlight.guess_language(self.code_after, self.path2)
            text_lines_a = self.code_before.splitlines()
            text_lines_b = self.code_after.splitlines()

            code_a = highlight.highlight(
                "\n".join(text_lines_a), language=language1, path=self.path1
            )
            code_b = highlight.highlight(
                "\n".join(text_lines_b), language=language2, path=self.path2
            )

            lines_a = code_a.split("\n")
            lines_b = code_b.split("\n")

            if self.code_before:
                for group in self.grouped_opcodes:
                    for tag, i1, i2, j1, j2 in group:
                        if tag == "replace" and (j2 - j1) / (i2 - i1) <= 1.5:
                            diff_lines_a, diff_lines_b = self._highlight_diff_lines(
                                lines_a[i1:i2], lines_b[j1:j2]
                            )
                            lines_a[i1:i2] = diff_lines_a
                            lines_b[j1:j2] = diff_lines_b

            self._highlighted_code_lines = (lines_a, lines_b)

        return self._highlighted_code_lines

    def get_title(self) -> Content:
        """Get a title for the diff view.

        Returns:
            A Content instance.
        """
        additions, removals = self.counts
        title = Content.from_markup(
            "📄 [dim]$path[/dim] ([$text-success][b]+$additions[/b][/], [$text-error][b]-$removals[/b][/])",
            path=self.path2,
            additions=additions,
            removals=removals,
            additions_label="addition" if additions == 1 else "additions",
            removals_label="removals" if removals == 1 else "removals",
        ).stylize_before("$text")
        return title

    def compose(self) -> ComposeResult:
        """Compose either split or unified view."""

        yield Static(self.get_title(), classes="title")
        if self.split:
            yield from self.compose_split()
        else:
            yield from self.compose_unified()

    def _check_auto_split(self, width: int):
        if self.auto_split:
            lines_a, lines_b = self.highlighted_code_lines
            split_width = max([line.cell_length for line in (lines_a + lines_b)]) * 2
            split_width += 4 + 2 * (
                max(
                    [
                        len(str(len(lines_a))),
                        len(str(len(lines_b))),
                    ]
                )
            )
            split_width += 3 * 2 if self.annotations else 2
            self.split = width >= split_width

    async def on_resize(self, event: events.Resize) -> None:
        self._check_auto_split(event.size.width)

    async def on_mount(self) -> None:
        self._check_auto_split(self.size.width)

    def compose_unified(self) -> ComposeResult:
        lines_a, lines_b = self.highlighted_code_lines

        for group in self.grouped_opcodes:
            line_numbers_a: list[int | None] = []
            line_numbers_b: list[int | None] = []
            annotations: list[str] = []
            code_lines: list[Content | None] = []
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for line_offset, line in enumerate(lines_a[i1:i2], 1):
                        annotations.append(" ")
                        line_numbers_a.append(i1 + line_offset)
                        line_numbers_b.append(j1 + line_offset)
                        code_lines.append(line)
                    continue
                if tag in {"delete", "replace"}:
                    for line_offset, line in enumerate(lines_a[i1:i2], 1):
                        annotations.append("-")
                        line_numbers_a.append(i1 + line_offset)
                        line_numbers_b.append(None)
                        code_lines.append(line)
                if tag in {"insert", "replace"}:
                    for line_offset, line in enumerate(lines_b[j1:j2], 1):
                        annotations.append("+")
                        line_numbers_a.append(None)
                        line_numbers_b.append(j1 + line_offset)
                        code_lines.append(line)

            NUMBER_STYLES = self.NUMBER_STYLES
            LINE_STYLES = self.LINE_STYLES

            line_number_width = max(
                len("" if line_no is None else str(line_no))
                for line_no in (line_numbers_a + line_numbers_b)
            )

            with containers.HorizontalGroup(classes="diff-group"):
                yield LineAnnotations(
                    [
                        (
                            Content(f" {' ' * line_number_width} ")
                            if line_no is None
                            else Content(f" {line_no:>{line_number_width}} ")
                        ).stylize(NUMBER_STYLES[annotation])
                        for line_no, annotation in zip(line_numbers_a, annotations)
                    ]
                )

                yield LineAnnotations(
                    [
                        (
                            Content(f" {' ' * line_number_width} ")
                            if line_no is None
                            else Content(f" {line_no:>{line_number_width}} ")
                        ).stylize(NUMBER_STYLES[annotation])
                        for line_no, annotation in zip(line_numbers_b, annotations)
                    ]
                )

                yield LineAnnotations(
                    [
                        (Content(f" {annotation} "))
                        .stylize(LINE_STYLES[annotation])
                        .stylize("bold")
                        for annotation in annotations
                    ],
                    classes="annotations",
                )
                code_line_styles = [
                    LINE_STYLES[annotation] for annotation in annotations
                ]
                with DiffScrollContainer():
                    yield DiffCode(LineContent(code_lines, code_line_styles))

    def compose_split(self) -> ComposeResult:
        lines_a, lines_b = self.highlighted_code_lines

        annotation_hatch = Content.styled("╲" * 3, "$foreground 15%")
        annotation_blank = Content(" " * 3)

        def make_annotation(
            annotation: Annotation, highlight_annotation: Literal["+", "-"]
        ) -> Content:
            """Format an annotation.

            Args:
                annotation: Annotation to format.
                highlight_annotation: Annotation to highlight ('+' or '-')

            Returns:
                Content with annotation.
            """
            if annotation == highlight_annotation:
                return (
                    Content(f" {annotation} ")
                    .stylize(self.LINE_STYLES[annotation])
                    .stylize("bold")
                )
            if annotation == "/":
                return annotation_hatch
            return annotation_blank

        for group in self.grouped_opcodes:
            line_numbers_a: list[int | None] = []
            line_numbers_b: list[int | None] = []
            annotations_a: list[Annotation] = []
            annotations_b: list[Annotation] = []
            code_lines_a: list[Content | None] = []
            code_lines_b: list[Content | None] = []
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for line_offset, line in enumerate(lines_a[i1:i2], 1):
                        annotations_a.append(" ")
                        annotations_b.append(" ")
                        line_numbers_a.append(i1 + line_offset)
                        line_numbers_b.append(j1 + line_offset)
                        code_lines_a.append(line)
                        code_lines_b.append(line)
                else:
                    if tag in {"delete", "replace"}:
                        for line_number, line in enumerate(lines_a[i1:i2], i1 + 1):
                            annotations_a.append("-")
                            line_numbers_a.append(line_number)
                            code_lines_a.append(line)
                    if tag in {"insert", "replace"}:
                        for line_number, line in enumerate(lines_b[j1:j2], j1 + 1):
                            annotations_b.append("+")
                            line_numbers_b.append(line_number)
                            code_lines_b.append(line)
                    fill_lists(code_lines_a, code_lines_b, None)
                    fill_lists(annotations_a, annotations_b, "/")
                    fill_lists(line_numbers_a, line_numbers_b, None)

            if line_numbers_a or line_numbers_b:
                line_number_width = max(
                    0 if line_no is None else len(str(line_no))
                    for line_no in (line_numbers_a + line_numbers_b)
                )
            else:
                line_number_width = 1

            hatch = Content.styled("╲" * (2 + line_number_width), "$foreground 15%")

            def format_number(line_no: int | None, annotation: str) -> Content:
                """Format a line number with an annotation.

                Args:
                    line_no: Line number or `None` if there is no line here.
                    annotation: An annotation string ('+', '-', or ' ')

                Returns:
                    Content for use in the `LineAnnotations` widget.
                """
                return (
                    hatch
                    if line_no is None
                    else Content(f" {line_no:>{line_number_width}} ").stylize(
                        self.NUMBER_STYLES[annotation]
                    )
                )

            with containers.HorizontalGroup(classes="diff-group"):
                # Before line numbers
                yield LineAnnotations(
                    starmap(format_number, zip(line_numbers_a, annotations_a))
                )
                # Before annotations
                yield LineAnnotations(
                    [make_annotation(annotation, "-") for annotation in annotations_a],
                    classes="annotations",
                )

                code_line_styles = [
                    self.LINE_STYLES[annotation] for annotation in annotations_a
                ]
                line_width = max(
                    line.cell_length
                    for line in code_lines_a + code_lines_b
                    if line is not None
                )
                # Before code
                with DiffScrollContainer() as scroll_container_a:
                    yield DiffCode(
                        LineContent(code_lines_a, code_line_styles, width=line_width)
                    )

                # After line numbers
                yield LineAnnotations(
                    starmap(format_number, zip(line_numbers_b, annotations_b))
                )
                # After annotations
                yield LineAnnotations(
                    [make_annotation(annotation, "+") for annotation in annotations_b],
                    classes="annotations",
                )

                code_line_styles = [
                    self.LINE_STYLES[annotation] for annotation in annotations_b
                ]
                # After code
                with DiffScrollContainer() as scroll_container_b:
                    yield DiffCode(
                        LineContent(code_lines_b, code_line_styles, width=line_width)
                    )

                # Link scroll containers, so they scroll together
                scroll_container_a.scroll_link = scroll_container_b
                scroll_container_b.scroll_link = scroll_container_a


if __name__ == "__main__":
    SOURCE1 = '''\
def loop_first(values: Iterable[T]) -> Iterable[tuple[bool, T]]:
\t"""Iterate and generate a tuple with a flag for first value."""
\titer_values = iter(values)
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
    from textual.widgets import Footer

    class DiffApp(App):
        BINDINGS = [
            ("space", "split", "Toggle split"),
            ("a", "toggle_annotations", "Toggle annotations"),
        ]

        def compose(self) -> ComposeResult:
            yield DiffView("foo.py", "foo.py", SOURCE1, SOURCE2)
            yield Footer()

        def action_split(self) -> None:
            self.query_one(DiffView).split = not self.query_one(DiffView).split

        def action_toggle_annotations(self) -> None:
            self.query_one(DiffView).annotations = not self.query_one(
                DiffView
            ).annotations

    app = DiffApp()
    app.run()
