from dataclasses import dataclass

from time import monotonic
from typing import Any, Callable

from textual.cache import LRUCache

from textual import on
from textual import events
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.selection import Selection
from textual.style import Style
from textual.geometry import Region, Size
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.timer import Timer


from toad import ansi


# Time required to double tab escape
ESCAPE_TAP_DURATION = 400 / 1000


class Terminal(ScrollView, can_focus=True):
    CURSOR_STYLE = Style.parse("reverse")

    hide_cursor = reactive(False)

    @dataclass
    class Finalized(Message):
        """Terminal was finalized."""

        terminal: Terminal

        @property
        def control(self) -> Terminal:
            return self.terminal

    @dataclass
    class AlternateScreenChanged(Message):
        """Terminal enabled or disabled alternate screen."""

        terminal: Terminal
        enabled: bool

        @property
        def control(self) -> Terminal:
            return self.terminal

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        minimum_terminal_width: int = 0,
        size: tuple[int, int] | None = None,
        get_terminal_dimensions: Callable[[], tuple[int, int]] | None = None,
    ):
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.minimum_terminal_width = minimum_terminal_width
        self._get_terminal_dimensions = get_terminal_dimensions

        self.state = ansi.TerminalState(self.write_process_stdin)

        if size is None:
            self._width = minimum_terminal_width or 80
            self._height: int = 24
        else:
            width, height = size
            self._width = width
            self._height = height

        self.minimum_terminal_width = self._width

        self.max_window_width = 0
        self._escape_time = monotonic()
        self._escaping = False
        self._escape_reset_timer: Timer | None = None
        self._finalized: bool = False
        self.current_directory: str | None = None
        self._alternate_screen: bool = False

        self._terminal_render_cache: LRUCache[tuple, Strip] = LRUCache(1024)
        self._write_to_stdin: Callable[[str], Any] | None = None

    @property
    def is_finalized(self) -> bool:
        """Finalized terminals will not accept writes or receive input."""
        return self._finalized

    @property
    def width(self) -> int:
        """Width of the terminal."""
        return self._width

    @property
    def height(self) -> int:
        """Height of the terminal."""
        return self._height

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    def set_state(self, state: ansi.TerminalState) -> None:
        """Set the terminal state, if this terminal is to inherit an existing state.

        Args:
            state: Terminal state object.
        """
        self.state = state

    def set_write_to_stdin(self, write_to_stdin: Callable[[str], Any]) -> None:
        """Set a callable which is invoked with input, to be sent to stdin.

        Args:
            write_to_stdin: Callable which takes a string.
        """
        self._write_to_stdin = write_to_stdin

    def finalize(self) -> None:
        """FInalize the terminal.

        The finalized terminal will reject new writes.
        Adds the TCSS class `-finalize`
        """
        if not self._finalized:
            self._finalized = True
            self.state.show_cursor = False
            self.add_class("-finalized")
            self._terminal_render_cache.clear()
            self.refresh()
            self.blur()
            self.post_message(self.Finalized(self))

    def allow_focus(self) -> bool:
        """Prohibit focus when the terminal is finalized and couldn't accept input."""
        return not self.is_finalized

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Get the text under the selection.

        Args:
            selection: Selection information.

        Returns:
            Tuple of extracted text and ending (typically "\n" or " "), or `None` if no text could be extracted.
        """
        text = "\n".join(
            line_record.content.plain for line_record in self.state.buffer.lines
        )
        return selection.extract(text), "\n"

    def _on_resize(self, event: events.Resize) -> None:
        if self._get_terminal_dimensions is None:
            width, height = self.scrollable_content_region.size
        else:
            width, height = self._get_terminal_dimensions()
        self.update_size(width, height)

    def update_size(self, width: int, height: int) -> None:
        old_width = self._width
        old_height = self._height
        self._terminal_render_cache.grow(height * 2)
        self._width = width or 80
        self._height = height or 24
        self._width = max(self._width, self.minimum_terminal_width)

        if (
            old_width != self._width
            or old_height != self._height
            and not self.is_finalized
        ):
            from toad.widgets.conversation import Conversation

            try:
                conversation = self.query_ancestor(Conversation)
            except NoMatches:
                pass
            else:
                conversation.shell.update_size(self._width, self._height)

        self.state.update_size(self._width, height)
        self._terminal_render_cache.clear()
        self.refresh()

    def on_mount(self) -> None:
        self.auto_links = False
        self.anchor()
        if self._get_terminal_dimensions is None:
            width, height = self.scrollable_content_region.size
        else:
            width, height = self._get_terminal_dimensions()
        self.update_size(width, height)

    def write(self, text: str) -> bool:
        """Write sequences to the terminal.

        Args:
            text: Text with ANSI escape sequences.

        Returns:
            `True` if the state visuals changed, `False` if no visual change.
        """

        scrollback_delta, alternate_delta = self.state.write(text)
        self._update_from_state(scrollback_delta, alternate_delta)
        scrollback_changed = bool(scrollback_delta is None or scrollback_delta)
        alternate_changed = bool(alternate_delta is None or alternate_delta)

        if self._alternate_screen != self.state.alternate_screen:
            self.post_message(
                self.AlternateScreenChanged(self, enabled=self.state.alternate_screen)
            )
        self._alternate_screen = self.state.alternate_screen
        return scrollback_changed or alternate_changed

    def on_click(self, event: events.Click) -> None:
        self.focus()
        event.stop()

    def _update_from_state(
        self, scrollback_delta: set[int] | None, alternate_delta: set[int] | None
    ) -> None:
        if self.state.current_directory:
            self.current_directory = self.state.current_directory
            self.finalize()
        width = self.state.width
        height = self.state.scrollback_buffer.height
        if self.state.alternate_screen:
            height += self.state.alternate_buffer.height
        self.virtual_size = Size(min(self.state.buffer.max_line_width, width), height)
        if self._anchored and not self._anchor_released:
            self.scroll_y = self.max_scroll_y

        scroll_y = int(self.scroll_y)
        visible_lines = frozenset(range(scroll_y, scroll_y + height))

        if scrollback_delta is None and alternate_delta is None:
            self.refresh()
        else:
            window_width = self.region.width
            scrollback_height = self.state.scrollback_buffer.line_count
            if scrollback_delta is None:
                self.refresh(Region(0, 0, window_width, scrollback_height))
            else:
                refresh_lines = [
                    Region(0, y - scroll_y, window_width, 1)
                    for y in sorted(scrollback_delta & visible_lines)
                ]
                if refresh_lines:
                    self.refresh(*refresh_lines)
            alternate_height = self.state.alternate_buffer.line_count
            if alternate_delta is None:
                self.refresh(
                    Region(
                        0,
                        scrollback_height - scroll_y,
                        window_width,
                        scrollback_height + alternate_height,
                    )
                )
            else:
                alternate_delta = {
                    line_no + scrollback_height for line_no in alternate_delta
                }
                refresh_lines = [
                    Region(0, y - scroll_y, window_width, 1)
                    for y in sorted(alternate_delta & visible_lines)
                ]
                if refresh_lines:
                    self.refresh(*refresh_lines)

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        strip = self._render_line(scroll_x, scroll_y + y, self._width)
        return strip

    def on_focus(self) -> None:
        self.border_subtitle = "Tap [b]esc[/b] [i]twice[/i] to exit"

    def on_blur(self) -> None:
        self.border_subtitle = "Click to focus"

    def _render_line(self, x: int, y: int, width: int) -> Strip:
        selection = self.text_selection
        visual_style = self.visual_style
        rich_style = visual_style.rich_style

        state = self.state
        buffer = state.scrollback_buffer
        buffer_offset = 0
        # If alternate screen is active place it (virtually) at the end
        if y >= len(buffer.folded_lines) and state.alternate_screen:
            buffer_offset = len(buffer.folded_lines)
            buffer = state.alternate_buffer
        # Get the folded line, which as a one to one relationship with y
        try:
            folded_line_ = buffer.folded_lines[y - buffer_offset]
            line_no, line_offset, offset, line, updates = folded_line_
        except IndexError:
            return Strip.blank(width, rich_style)

        line_record = buffer.lines[line_no]
        cache_key: tuple | None = (
            self.state.alternate_screen,
            y,
            line_record.updates,
            updates,
        )

        # Add in cursor
        if (
            not self.hide_cursor
            and state.show_cursor
            and buffer.cursor_line == y - buffer_offset
        ):
            if buffer.cursor_offset >= len(line):
                line = line.pad_right(buffer.cursor_offset - len(line) + 1)
            line_cursor_offset = buffer.cursor_offset
            line = line.stylize(
                self.CURSOR_STYLE, line_cursor_offset, line_cursor_offset + 1
            )
            cache_key = None

        # get cached strip if there is no selection
        if (
            not selection
            and cache_key is not None
            and (strip := self._terminal_render_cache.get(cache_key))
        ):
            strip = strip.crop(x, x + width)
            strip = strip.adjust_cell_length(
                width, (visual_style + line_record.style).rich_style
            )
            strip = strip.apply_offsets(x + offset, line_no)
            return strip

        # Apply selection
        if selection is not None and (select_span := selection.get_span(line_no)):
            unfolded_content = line_record.content.expand_tabs(8)
            start, end = select_span
            if end == -1:
                end = len(unfolded_content)
            selection_style = self.screen.get_visual_style("screen--selection")
            unfolded_content = unfolded_content.stylize(selection_style, start, end)
            try:
                folded_lines = self.state._fold_line(line_no, unfolded_content, width)
                line = folded_lines[line_offset].content
                cache_key = None
            except IndexError:
                pass

        try:
            strip = Strip(
                line.render_segments(visual_style), cell_length=line.cell_length
            )
        except Exception:
            # TODO: Is this neccesary?
            strip = Strip.blank(line.cell_length)

        if cache_key is not None:
            self._terminal_render_cache[cache_key] = strip

        strip = strip.crop(x, x + width)
        strip = strip.adjust_cell_length(
            width, (visual_style + line_record.style).rich_style
        )
        strip = strip.apply_offsets(x + offset, line_no)

        return strip

    def _reset_escaping(self) -> None:
        if self._escaping:
            self.write_process_stdin(self.state.key_escape())
        self._escaping = False

    def on_key(self, event: events.Key):
        event.prevent_default()
        event.stop()

        if event.key == "escape":
            if self._escaping:
                if monotonic() < self._escape_time + ESCAPE_TAP_DURATION:
                    self.blur()
                    self._escaping = False
                    return
                else:
                    self.write_process_stdin(self.state.key_escape())
            else:
                self._escaping = True
                self._escape_time = monotonic()
                self._escape_reset_timer = self.set_timer(
                    ESCAPE_TAP_DURATION, self._reset_escaping
                )
                return
        else:
            self._reset_escaping()
            if self._escape_reset_timer is not None:
                self._escape_reset_timer.stop()

        if (stdin := self.state.key_event_to_stdin(event)) is not None:
            self.write_process_stdin(stdin)

    @property
    def allow_select(self) -> bool:
        return self.is_finalized or not self._alternate_screen

    def _encode_mouse_event_sgr(self, event: events.MouseEvent) -> str:
        x = int(event.x)
        y = int(event.y)

        if isinstance(event, events.MouseMove):
            button = event.button + 32 if event.button else 35
        else:
            button = event.button - 1
            if button >= 4:
                button = button - 4 + 128
            if event.shift:
                button += 4
            if event.meta:
                button += 8
            if event.ctrl:
                button += 16

        if isinstance(event, events.MouseDown):
            final_character = "M"
        elif isinstance(event, events.MouseUp):
            button = 0
            final_character = "m"
        else:
            final_character = "M"
        mouse_stdin = f"\x1b[<{button};{x + 1};{y + 1}{final_character}"
        return mouse_stdin

    @on(events.MouseMove)
    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self.is_finalized:
            return
        if (mouse_tracking := self.state.mouse_tracking) is None:
            return
        if mouse_tracking.tracking == "all" or (
            event.button and mouse_tracking.tracking == "drag"
        ):
            self._handle_mouse_event(event)
            event.prevent_default()
            event.stop()

    @on(events.MouseDown)
    @on(events.MouseUp)
    def on_mouse_button(self, event: events.MouseUp | events.MouseDown) -> None:
        if self.is_finalized:
            return
        if self.state.mouse_tracking is None:
            return
        self._handle_mouse_event(event)
        event.prevent_default()
        event.stop()

    def _handle_mouse_event(self, event: events.MouseEvent) -> None:
        if (mouse_tracking := self.state.mouse_tracking) is None:
            return
        # TODO: Other mouse tracking formats
        match mouse_tracking.format:
            case "sgr":
                self.write_process_stdin(self._encode_mouse_event_sgr(event))

    def on_paste(self, event: events.Paste) -> None:
        for character in event.text:
            self.write_process_stdin(character)

    def write_process_stdin(self, input: str) -> None:
        if self._write_to_stdin is not None:
            self._write_to_stdin(input)


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    TEST = (
        "\033[31mThis is red text\033[0m\n"
        "\033[32mThis is green text\033[0m\n"
        "\033[33mThis is yellow text\033[0m\n"
        "\033[34mThis is blue text\033[0m\n"
        "\033[35mThis is magenta text\033[0m\n"
        "\033[36mThis is cyan text\033[0m\n"
        "\033[1mThis is bold text\033[0m\n"
        "\033[4mThis is underlined text\033[0m\n"
        "\033[1;31mThis is bold red text\033[0m\n"
        "\033[42mThis has a green background\033[0m\n"
        "\033[97;44mWhite text on blue background\033[0m"
    )

    class TApp(App):
        def compose(self) -> ComposeResult:
            yield Terminal()

        def on_mount(self) -> None:
            terminal = self.query_one(Terminal)
            terminal.write(TEST)

    app = TApp()
    app.run()
