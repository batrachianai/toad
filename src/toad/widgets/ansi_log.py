from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Iterable, NamedTuple, Sequence


from textual.geometry import Size, Region
from textual.cache import LRUCache

from textual.content import Content
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.selection import Selection
from textual.filter import LineFilter

from toad.ansi import ANSIStream
from toad.menus import MenuItem


class LineFold(NamedTuple):
    line_no: int
    """The line number."""

    line_offset: int
    """The index of the folded line."""

    offset: int
    """The offset within the original line."""

    content: Content
    """The content."""


@dataclass
class LineRecord:
    content: Content
    folds: list[LineFold] = field(default_factory=list)
    updates: int = 0


class ANSILog(ScrollView, can_focus=False):
    DEFAULT_CSS = """
    ANSILog {
        overflow: auto auto;
        scrollbar-gutter: stable;
        height: 1fr;        
    }
    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        minimum_terminal_width: int = -1,
    ):
        self.line_start = 0
        self.minimum_terminal_width = minimum_terminal_width

        self.cursor_line = 0
        """folded line index."""
        self.cursor_offset = 0
        """folded line offset"""

        # Sequence of lines
        self._lines: list[LineRecord] = []

        # Maps the line index on to the folder lines index
        self._line_to_fold: list[int] = []

        # List of folded lines, one per line in the widget
        self._folded_lines: list[LineFold] = []

        # Cache of segments
        self._render_line_cache: LRUCache[tuple, Strip] = LRUCache(1000 * 4)

        # ANSI stream
        self._ansi_stream = ANSIStream()

        self.max_line_width = 0
        self.max_window_width = 0
        self._reflow_width: int | None = None

        self._width = 80

        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

    @property
    def current_directory(self) -> str:
        return self._ansi_stream.current_directory

    def _update_width(self) -> None:
        window_width = self.scrollable_content_region.width or 80
        self.max_window_width = max(self.max_window_width, window_width)
        if self.minimum_terminal_width == -1 and window_width:
            self.minimum_terminal_width = window_width
        width = max(
            self.minimum_terminal_width,
            max(min(self.max_line_width, self.max_window_width), window_width),
        )
        self._width = width

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def last_line_index(self) -> int:
        return self.line_count - 1

    @property
    def cursor_line_offset(self) -> int:
        """The cursor offset within the un-folded lines."""
        cursor_folded_line = self._folded_lines[self.cursor_line]
        cursor_line_offset = cursor_folded_line.line_offset
        line_no = cursor_folded_line.line_no
        line = self._lines[line_no]
        position = 0
        for folded_line_offset, folded_line in enumerate(line.folds):
            if folded_line_offset == cursor_line_offset:
                position += self.cursor_offset
                break
            position += len(folded_line.content)
        return position

    def get_block_menu(self) -> Iterable[MenuItem]:
        return
        yield

    #     yield MenuItem("Copy to clipboard", "copy_to_clipboard", "c")
    #     yield MenuItem("Copy to prompt", "copy_to_prompt", "p")

    def action_copy_to_clipboard(self) -> None:
        self.notify("Copy to clipboard")

    def get_block_content(self, destination: str) -> str | None:
        text_content = "\n".join(
            [line.content.plain.expandtabs() for line in self._lines]
        )
        if destination == "prompt":
            return f"```\n{text_content}\n```"
        else:
            return text_content

    def get_line_filters(self) -> Sequence[LineFilter]:
        return []

    def on_mount(self):
        self.anchor()
        self._update_width()

    def notify_style_update(self) -> None:
        super().notify_style_update()
        self._clear_caches()
        self._reflow()

    def allow_select(self) -> bool:
        return True

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Get the text under the selection.

        Args:
            selection: Selection information.

        Returns:
            Tuple of extracted text and ending (typically "\n" or " "), or `None` if no text could be extracted.
        """
        text = "\n".join(line_record.content.plain for line_record in self._lines)
        return selection.extract(text), "\n"

    def _clear_caches(self) -> None:
        self._render_line_cache.clear()

    def on_resize(self) -> None:
        if self._width != self._reflow_width:
            self._update_width()
            self._reflow()
            self._reflow_width = self._width
            self._clear_caches()

    def clear(self) -> None:
        self._lines.clear()
        self._folded_lines.clear()
        self._clear_caches()
        self.line_start = 0
        self.refresh()

    def write(self, text: str) -> bool:
        """Write to the log.

        Args:
            text: New text (and escape sequences).

        Returns:
            `True` if the log output changed, otherwise `False`.
        """
        if not text:
            return False
        folded_lines = self._folded_lines

        added_content = False
        for ansi_token in self._ansi_stream.feed(text):
            (
                delta_x,
                delta_y,
                absolute_x,
                absolute_y,
                content,
                replace,
                clear,
            ) = ansi_token
            while self.cursor_line >= len(folded_lines):
                self.add_line(Content())
                added_content = True

            folded_line = folded_lines[self.cursor_line]
            previous_content = folded_line.content
            line = self._lines[folded_line.line_no]

            if content is not None:
                cursor_line_offset = self.cursor_line_offset

                if replace is not None:
                    start_replace, end_replace = ansi_token.get_replace_offsets(
                        cursor_line_offset, len(line.content)
                    )
                    updated_line = Content.assemble(
                        line.content[:start_replace],
                        content,
                        line.content[end_replace + 1 :],
                    )

                else:
                    if cursor_line_offset == len(line.content):
                        updated_line = line.content + content
                    else:
                        updated_line = Content.assemble(
                            line.content[:cursor_line_offset],
                            content,
                            line.content[cursor_line_offset + len(content) :],
                        )

                self.update_line(folded_line.line_no, updated_line)
                if not previous_content.is_same(folded_line.content):
                    added_content = True

            if delta_x is not None:
                self.cursor_offset += delta_x
                while self.cursor_offset > self._width:
                    self.cursor_line += 1
                    self.cursor_offset -= self._width
            if delta_y is not None:
                self.cursor_line = max(0, self.cursor_line + delta_y)
            if absolute_x is not None:
                self.cursor_offset = absolute_x
            if absolute_y is not None:
                self.cursor_line = max(0, absolute_y)
        return added_content

    def _fold_line(self, line_no: int, line: Content, width: int) -> list[LineFold]:
        if not width:
            return [LineFold(0, 0, 0, line)]
        line_length = line.cell_length
        if line_length <= width:
            return [LineFold(line_no, 0, 0, line)]
        divide_offsets = list(range(width, line_length, width))
        folded_lines = [folded_line for folded_line in line.divide(divide_offsets)]
        offsets = [0, *divide_offsets]
        folds = [
            LineFold(line_no, line_offset, offset, folded_line)
            for line_offset, (offset, folded_line) in enumerate(
                zip(offsets, folded_lines)
            )
        ]
        assert len(folds)
        return folds

    def _update_virtual_size(self) -> None:
        self.virtual_size = Size(self._width, len(self._folded_lines))

    def _reflow(self) -> None:
        width = self._width
        if not width:
            self._clear_caches()
            return

        folded_lines = self._folded_lines = []
        folded_lines.clear()
        self._line_to_fold.clear()
        for line_no, line_record in enumerate(self._lines):
            line_expanded_tabs = line_record.content.expand_tabs(8)
            line_record.folds[:] = self._fold_line(line_no, line_expanded_tabs, width)
            line_record.updates += 1
            self._line_to_fold.append(len(self._folded_lines))
            self._folded_lines.extend(line_record.folds)
        self._update_virtual_size()

    def add_line(self, content: Content) -> None:
        line_no = self.line_count
        width = self._width
        line_record = LineRecord(content, self._fold_line(line_no, content, width))
        self._lines.append(line_record)
        # if not width:
        #     return
        folds = line_record.folds
        self._line_to_fold.append(len(self._folded_lines))
        self._folded_lines.extend(folds)

    def update_line(self, line_index: int, line: Content) -> None:
        while line_index >= len(self._lines):
            self.add_line(Content())

        line_expanded_tabs = line.expand_tabs(8)
        self.max_line_width = max(line_expanded_tabs.cell_length, self.max_line_width)

        line_record = self._lines[line_index]
        line_record.content = line
        line_record.folds[:] = self._fold_line(
            line_index, line_expanded_tabs, self._width
        )
        line_record.updates += 1

        fold_line = self._line_to_fold[line_index]
        del self._line_to_fold[line_index:]
        del self._folded_lines[fold_line:]

        refresh_lines = 0

        for line_no in range(line_index, self.line_count):
            line_record = self._lines[line_no]
            line_record.updates += 1
            self._line_to_fold.append(len(self._folded_lines))
            for fold in line_record.folds:
                self._folded_lines.append(fold)
                refresh_lines += 1

        self.refresh(Region(0, line_no, self._width, refresh_lines))

    def on_idle(self):
        self._update_width()
        self._update_virtual_size()

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        strip = self._render_line(scroll_x, scroll_y + y, self._width)
        return strip

    def _render_line(self, x: int, y: int, width: int) -> Strip:
        selection = self.text_selection

        visual_style = self.visual_style
        rich_style = visual_style.rich_style

        try:
            line_no, line_offset, offset, line = self._folded_lines[y]
        except IndexError:
            return Strip.blank(width, rich_style)

        unfolded_line = self._lines[line_no]
        cache_key = (self.scroll_offset.y - y, unfolded_line.updates)
        if not selection:
            cached_strip = self._render_line_cache.get(cache_key)
            if cached_strip is not None:
                cached_strip = cached_strip.crop_extend(x, x + width, rich_style)
                cached_strip = cached_strip.apply_offsets(x + offset, line_no)
                return cached_strip

        if selection is not None:
            if select_span := selection.get_span(line_no):
                unfolded_content = self._lines[line_no].content.expand_tabs(8)
                start, end = select_span
                if end == -1:
                    end = len(unfolded_content)
                selection_style = self.screen.get_visual_style("screen--selection")
                unfolded_content = unfolded_content.stylize(selection_style, start, end)
                try:
                    line = (
                        self._fold_line(line_no, unfolded_content, width)[line_offset]
                    ).content
                except IndexError:
                    pass

        strip = Strip(
            line.render_segments(self.visual_style), cell_length=line.cell_length
        )

        if not selection:
            self._render_line_cache[cache_key] = strip
        strip = strip.crop_extend(x, x + width, rich_style)
        strip = strip.apply_offsets(x + offset, line_no)

        return strip


if __name__ == "__main__":
    from textual import work
    from textual.app import App, ComposeResult
    from textual import containers

    import asyncio

    import codecs

    class ANSIApp(App):
        CSS = """
        ANSILog {
          
        }
        """

        def compose(self) -> ComposeResult:
            with containers.VerticalScroll():
                yield ANSILog()

        @work
        async def on_mount(self) -> None:
            ansi_log = self.query_one(ANSILog)
            env = os.environ.copy()
            env["LINES"] = "50"
            env["COLUMNS"] = str(self.size.width - 2)
            env["TTY_COMPATIBLE"] = "1"
            env["FORCE_COLOR"] = "1"

            process = await asyncio.create_subprocess_shell(
                # "python -m rich.palette;python -m rich.palette;",
                "python ansi_mandel.py",
                # "python simple_test.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            assert process.stdout is not None
            unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            while data := await process.stdout.read(16 * 1024):
                line = unicode_decoder.decode(data)
                ansi_log.write(line)
            line = unicode_decoder.decode(b"", final=True)
            ansi_log.write(line)

    ANSIApp().run()
