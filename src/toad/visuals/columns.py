from __future__ import annotations

from typing import Literal
from fractions import Fraction

import rich.repr
from rich.segment import Segment

from textual.content import Content
from textual.css.styles import RulesMap
from textual.visual import Visual, RenderOptions
from textual.strip import Strip
from textual.style import Style

from toad._loop import loop_last


@rich.repr.auto
class Row(Visual):
    """A visual for a row produced by `columns`.

    No need to construct these manually, they are returned from the Columns `__getindex__`

    """

    def __init__(self, columns: Columns, row_index: int) -> None:
        """

        Args:
            columns: The parent Columns instance.
            row_index: Index of the row within columns.
        """
        self.columns = columns
        self.row_index = row_index

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.columns
        yield self.row_index

    def render_strips(
        self, width: int, height: int | None, style: Style, options: RenderOptions
    ) -> list[Strip]:
        strips = self.columns.render(self.row_index, width, style)
        return strips

    def get_optimal_width(self, rules: RulesMap, container_width: int) -> int:
        return min(container_width, self.columns.get_optimal_width())

    def get_height(self, rules: RulesMap, width: int) -> int:
        return self.columns.get_row_height(width, self.row_index)


@rich.repr.auto
class Columns:
    """Renders columns of Content."""

    def __init__(
        self,
        *columns: Literal["auto", "flex"],
        gutter: int = 1,
        style: Style | str = "",
    ) -> None:
        """

        Args:
            *columns: "auto" to use the maximum width of the cells in a column,
                or "flex" to use the remaining space.
            gutter: Space between columns in cells.
            style: Base style for the columns.
        """
        self.columns = columns
        self.gutter = gutter
        self.style = style
        self.rows: list[list[Content]] = []
        self._last_render_parameters: tuple[int, Style] = (-1, Style())
        self._last_render: list[list[Strip]] | None = None
        self._optimal_width_cache: int | None = None

    def __rich_repr__(self) -> rich.repr.Result:
        for column in self.columns:
            yield column
        yield "gutter", self.gutter, 1
        yield "style", self.style, ""

    def __getitem__(self, row_index: int) -> Row:
        if row_index < 0:
            row_index = len(self.rows) - row_index
        if row_index >= len(self.rows):
            raise IndexError(f"No row with index {row_index}")
        return Row(self, row_index)

    def get_optimal_width(self) -> int:
        """Get optional width (Visual protocol).

        Returns:
            Width in cells.
        """
        if self._optimal_width_cache is not None:
            return self._optimal_width_cache
        gutter_width = (len(self.columns) - 1) * self.gutter
        optimal_width = max(
            sum(content.cell_length for content in row) + gutter_width
            for row in self.rows
        )
        self._optimal_width_cache = optimal_width
        return optimal_width

    def get_row_height(self, width: int, row_index: int) -> int:
        """Get the height of a row when rendered with the given width.

        Args:
            width: Available width.
            row_index: Index of the row.

        Returns:
            Height in lines of the row.
        """
        if self._last_render is None:
            row_strips = self._render(width, Style.null())
        else:
            row_strips = self._last_render
        return len(row_strips[row_index])

    def add_row(self, *cells: Content | str) -> Row:
        """Add a row.

        Args:
            *cells: Cell content.

        Returns:
            A Row renderable.

        """
        assert len(cells) == len(self.columns)
        new_cells = [
            cell if isinstance(cell, Content) else Content(cell) for cell in cells
        ]
        self.rows.append(new_cells)
        self._optimal_width_cache = None
        self._last_render = None
        return Row(self, len(self.rows) - 1)

    def render(
        self, row_index: int, render_width: int, style: Style = Style.null()
    ) -> list[Strip]:
        """render a row given by its index.

        Args:
            row_index: Index of the row.
            render_width: Width of the render.
            style: Base style to render.

        Returns:
            A list of strips, which may be returned from a visual.
        """
        cache_key = (render_width, style)
        if self._last_render_parameters == cache_key and self._last_render is not None:
            row_strips = self._last_render
        else:
            row_strips = self._last_render = self._render(render_width, style)
            self._last_render_parameters = cache_key
        return row_strips[row_index]

    def _render(self, render_width: int, style: Style) -> list[list[Strip]]:
        """Render a row.

        Args:
            render_width: Width of render.
            style: Base Style.

        Returns:
            A list of list of Strips (one list of strips per row).
        """
        gutter_width = (len(self.columns) - 1) * self.gutter
        widths: list[int | None] = []

        for index, column in enumerate(self.columns):
            if column == "auto":
                widths.append(max(row[index].cell_length for row in self.rows))
            else:
                widths.append(None)

        if any(width is None for width in widths):
            used_width = sum(width for width in widths if width is not None)
            remaining_width = Fraction(render_width - gutter_width - used_width)
            if remaining_width <= 0:
                widths = [width or 0 for width in widths]
            else:
                remaining_count = sum(1 for width in widths if width is None)
                cell_width = remaining_width / remaining_count

                distribute: list[int] = []
                previous_width = 0
                total = Fraction(0)
                for _ in range(remaining_count):
                    total += cell_width
                    distribute.append(int(total) - previous_width)
                    previous_width = int(total)

                iter_distribute = iter(distribute)
                for index, column_width in enumerate(widths.copy()):
                    if column_width is None:
                        widths[index] = int(next(iter_distribute))

        row_strips: list[list[Strip]] = []

        for row in self.rows:
            column_renders: list[list[list[Segment]]] = []
            for content_width, content in zip(widths, row):
                assert content_width is not None
                segments = [
                    line.truncate(content_width, pad=True).render_segments(style)
                    for line in content.wrap(content_width)
                ]

                column_renders.append(segments)

            height = max(len(lines) for lines in column_renders)
            rich_style = style.rich_style
            for width, lines in zip(widths, column_renders):
                assert width is not None
                while len(lines) < height:
                    lines.append([Segment(" " * width, rich_style)])

            gutter = Segment(" " * self.gutter, rich_style)
            strips: list[Strip] = []
            for line_no in range(height):
                strip_segments: list[Segment] = []
                for last, column in loop_last(column_renders):
                    strip_segments.extend(column[line_no])
                    if not last and gutter:
                        strip_segments.append(gutter)
                strips.append(Strip(strip_segments, render_width))

            row_strips.append(strips)

        return row_strips


if __name__ == "__main__":
    from rich import traceback

    traceback.install(show_locals=True)

    from textual.app import App, ComposeResult
    from textual.widgets import Static

    columns = Columns("auto", "flex")
    columns.add_row("Foo", "Hello, World! " * 20)

    class CApp(App):
        DEFAULT_CSS = """
        .row1 {
            background: blue;
           
        }
        """

        def compose(self) -> ComposeResult:
            yield Static(columns[0], classes="row1")

    CApp().run()
