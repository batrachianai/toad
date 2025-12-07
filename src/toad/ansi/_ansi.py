from __future__ import annotations

import io
from itertools import accumulate
import re

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Iterable, Literal, Mapping, NamedTuple

import rich.repr

from textual import events
from textual.color import Color
from textual.content import Content, EMPTY_CONTENT
from textual.geometry import clamp
from textual.style import Style, NULL_STYLE

from toad.ansi._ansi_colors import ANSI_COLORS
from toad.ansi._keys import TERMINAL_KEY_MAP, CURSOR_KEYS_APPLICATION
from toad.ansi._control_codes import CONTROL_CODES
from toad.ansi._sgr_styles import SGR_STYLES
from toad.ansi._stream_parser import (
    StreamParser,
    SeparatorToken,
    PatternToken,
    Pattern,
    PatternCheck,
    ParseResult,
    Token,
)

from toad.dec import CHARSET_MAP


def character_range(start: int, end: int) -> frozenset:
    """Build a set of characters between to code-points.

    Args:
        start: Start codepoint.
        end: End codepoint (inclusive)

    Returns:
        A frozenset of the characters..
    """
    return frozenset(map(chr, range(start, end + 1)))


class ANSIToken:
    pass


class DEC(NamedTuple):
    slot: int
    character_set: str


class DECInvoke(NamedTuple):
    gl: int | None = None
    gr: int | None = None
    shift: int | None = None


DEC_SLOTS = {"(": 0, ")": 1, "*": 2, "+": 3, "-": 1, ".": 2, "//": 3}


def show(obj: object) -> object:
    print(obj)
    return obj


class FEPattern(Pattern):
    FINAL = character_range(0x30, 0x7E)
    INTERMEDIATE = character_range(0x20, 0x2F)
    CSI_TERMINATORS = character_range(0x40, 0x7E)
    OSC_TERMINATORS = frozenset({"\x07", "\x9c"})
    DSC_TERMINATORS = frozenset({"\x9c"})

    def check(self) -> PatternCheck:
        sequence = io.StringIO()
        store = sequence.write
        store(character := (yield))

        match character:
            # CSI
            case "[":
                CSI_TERMINATORS = self.CSI_TERMINATORS
                while (character := (yield)) not in CSI_TERMINATORS:
                    store(character)
                store(character)
                return ("csi", sequence.getvalue())

            # OSC
            case "]":
                last_character = ""
                OSC_TERMINATORS = self.OSC_TERMINATORS
                while (character := (yield)) not in OSC_TERMINATORS:
                    store(character)
                    if last_character == "\x1b" and character in {"\\", "\0x5c"}:
                        break
                    last_character = character
                store(character)

                return ("osc", sequence.getvalue())

            # DCS
            case "P":
                print("TODO DCS")
                last_character = ""
                DSC_TERMINATORS = self.DSC_TERMINATORS
                while (character := (yield)) not in DSC_TERMINATORS:
                    store(character)
                    if last_character == "\x1b" and character == "\\":
                        break
                    last_character = character
                store(character)
                return ("dcs", sequence.getvalue())

            # Character set designation
            case "(" | ")" | "*" | "+" | "-" | "." | "/":
                if (character := (yield)) not in self.FINAL:
                    return False
                store(character)
                return ("dec", sequence.getvalue())

            case "n" | "o" | "~" | "}" | "|" | "N" | "O":
                return ("dec_invoke", sequence.getvalue())

            # Line attribute
            case "#":
                print("LINE ATTRIBUTES")
                store((yield))
                return ("la", sequence.getvalue())
            # ISO 2022: ESC SP
            case " ":
                store((yield))
                return ("sp", sequence.getvalue())
            case _:
                return ("control", character)


class ANSIParser(StreamParser[tuple[str, str]]):
    """Parse a stream of text containing escape sequences in to logical tokens."""

    def parse(self) -> ParseResult[tuple[str, str]]:
        NEW_LINE = "\n"
        CARRIAGE_RETURN = "\r"
        ESCAPE = "\x1b"
        BACKSPACE = "\x08"

        while True:
            token = yield self.read_until(NEW_LINE, CARRIAGE_RETURN, ESCAPE, BACKSPACE)
            if isinstance(token, SeparatorToken):
                if token.text == ESCAPE:
                    token = yield self.read_patterns("\x1b", fe=FEPattern())
                    if isinstance(token, PatternToken):
                        yield token.value
                else:
                    yield "separator", token.text
                continue

            yield "content", token.text


EMPTY_LINE = Content()


type ClearType = Literal["cursor_to_end", "cursor_to_beginning", "screen", "scrollback"]
ANSI_CLEAR: Mapping[int, ClearType] = {
    0: "cursor_to_end",
    1: "cursor_to_beginning",
    2: "screen",
    3: "scrollback",
}


@rich.repr.auto
class ANSIContent(NamedTuple):
    """Content to be written to the terminal."""

    text: str

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.text


@rich.repr.auto
class ANSICursor(NamedTuple):
    """Represents a single operation on the ANSI output.

    All values may be `None` meaning "not set".
    """

    delta_x: int | None = None
    """Relative x change."""
    delta_y: int | None = None
    """Relative y change."""
    absolute_x: int | None = None
    """Replace x."""
    absolute_y: int | None = None
    """Replace y."""
    erase: bool = False
    """Erase (replace with spaces)?"""
    clear_range: tuple[int | None, int | None] | None = None
    """Replace range (slice like)."""
    relative: bool = False
    """Should replace be relative (`False`) or absolute (`True`)"""
    update_background: bool = False
    """Optional style for remaining line."""
    auto_scroll: bool = False
    """Perform a scroll with the movement?"""

    def __rich_repr__(self) -> rich.repr.Result:
        yield "delta_x", self.delta_x, None
        yield "delta_y", self.delta_y, None
        yield "absolute_x", self.absolute_x, None
        yield "absolute_y", self.absolute_y, None
        yield "erase", self.erase, False
        yield "clear_range", self.clear_range, None
        yield "relative", self.relative, False
        yield "update_background", self.update_background, False
        yield "auto_scroll", self.auto_scroll, False

    @lru_cache(maxsize=1024)
    def get_clear_offsets(
        self, cursor_offset: int, line_length: int
    ) -> tuple[int, int]:
        """Get replace offsets.

        Args:
            cursor_offset: Current cursor offset.
            line_length: Length of line.

        Returns:
            A pair of offsets (inclusive).
        """
        assert self.clear_range is not None, (
            "Only call this if the replace attribute has a value"
        )
        replace_start, replace_end = self.clear_range
        if replace_start is None:
            replace_start = cursor_offset
        if replace_end is None:
            replace_end = cursor_offset
        if replace_start < 0:
            replace_start = line_length + replace_start
        if replace_end < 0:
            replace_end = line_length + replace_end
        if self.relative:
            return (cursor_offset + replace_start, cursor_offset + replace_end)
        else:
            return (replace_start, replace_end)


@rich.repr.auto
class ANSINewLine:
    """New line (diffrent in alternate buffer)"""


@rich.repr.auto
class ANSIStyle(NamedTuple):
    """Update style."""

    style: Style

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.style


@rich.repr.auto
class ANSIClear(NamedTuple):
    """Enumeration for clearing the 'screen'."""

    clear: ClearType

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.clear


@rich.repr.auto
class ANSIScrollMargin(NamedTuple):
    """Set the scroll margin."""

    top: int | None = None
    bottom: int | None = None

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.top
        yield self.bottom


@rich.repr.auto
class ANSIScroll(NamedTuple):
    """Scroll buffer."""

    direction: Literal[+1, -1]
    lines: int

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.direction
        yield self.lines


class ANSIFeatures(NamedTuple):
    """Terminal feature flags."""

    show_cursor: bool | None = None
    alternate_screen: bool | None = None
    bracketed_paste: bool | None = None
    cursor_blink: bool | None = None
    cursor_keys: bool | None = None
    replace_mode: bool | None = None
    auto_wrap: bool | None = None


MOUSE_TRACKING_MODES = Literal["button", "drag", "all"]
MOUSE_FORMAT = Literal["normal", "utf8", "sgr", "urxvt"]


class ANSIMouseTracking(NamedTuple):
    """Set mouse tracking."""

    mode: Literal["none"] | MOUSE_TRACKING_MODES | None = None
    format: MOUSE_FORMAT | None = None
    focus_events: bool | None = None
    alternate_scroll: bool | None = None


# Not technically part of the terminal protocol
@rich.repr.auto
class ANSIWorkingDirectory(NamedTuple):
    """Working directory changed"""

    path: str

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.path


@rich.repr.auto
class ANSICharacterSet(NamedTuple):
    """Updated character set state."""

    dec: DEC | None = None
    dec_invoke: DECInvoke | None = None


@rich.repr.auto
class ANSICursorPositionRequest(NamedTuple):
    pass


type ANSICommand = (
    ANSIStyle
    | ANSIContent
    | ANSICursor
    | ANSINewLine
    | ANSIClear
    | ANSIScrollMargin
    | ANSIScroll
    | ANSIWorkingDirectory
    | ANSICharacterSet
    | ANSIFeatures
    | ANSIMouseTracking
    | ANSICursorPositionRequest
)


class ANSIStream:
    def __init__(self) -> None:
        self.parser = ANSIParser()
        self.style = NULL_STYLE
        self.show_cursor = True

    @classmethod
    @lru_cache(maxsize=1024)
    def _parse_sgr(cls, sgr: str) -> Style | None:
        """Parse a SGR (Select Graphics Rendition) code in to a Style instance,
        or `None` to indicate a reset.

        Args:
            sgr: SGR sequence.

        Returns:
            A Visual Style, or `None`.
        """
        codes = [
            code if code < 255 else 255
            for code in map(int, [sgr_code or "0" for sgr_code in sgr.split(";")])
        ]
        style = NULL_STYLE
        while codes:
            match codes:
                case [38, 2, red, green, blue, *codes]:
                    # Foreground RGB
                    style += Style(foreground=Color(red, green, blue))
                case [48, 2, red, green, blue, *codes]:
                    # Background RGB
                    style += Style(background=Color(red, green, blue))
                case [38, 5, ansi_color, *codes]:
                    # Foreground ANSI
                    style += Style(foreground=ANSI_COLORS[ansi_color])
                case [48, 5, ansi_color, *codes]:
                    # Background ANSI
                    style += Style(background=ANSI_COLORS[ansi_color])
                case [0, *codes]:
                    # reset
                    return None
                case [code, *codes]:
                    if sgr_style := SGR_STYLES.get(code):
                        style += sgr_style

        return style

    def feed(self, text: str) -> Iterable[ANSICommand]:
        """Feed text potentially containing ANSI sequences, and parse in to
        an iterable of ansi commands.

        Args:
            text: Text to feed.

        Yields:
            `ANSICommand` instances.
        """

        for token in self.parser.feed(text):
            if not isinstance(token, Token):
                yield from self.on_token(token)

    ANSI_SEPARATORS = {
        "\n": ANSICursor(delta_y=+1, absolute_x=0),
        "\r": ANSICursor(absolute_x=0),
        "\x08": ANSICursor(delta_x=-1),
    }
    CLEAR_LINE_CURSOR_TO_END = ANSICursor(
        clear_range=(None, -1), erase=True, update_background=True
    )
    CLEAR_LINE_CURSOR_TO_BEGINNING = ANSICursor(
        clear_range=(0, None), erase=True, update_background=True
    )
    CLEAR_LINE = ANSICursor(clear_range=(0, -1), erase=True, update_background=True)
    CLEAR_SCREEN_CURSOR_TO_END = ANSIClear("cursor_to_end")
    CLEAR_SCREEN_CURSOR_TO_BEGINNING = ANSIClear("cursor_to_beginning")
    CLEAR_SCREEN = ANSIClear("screen")
    CLEAR_SCREEN_SCROLLBACK = ANSIClear("scrollback")
    SHOW_CURSOR = ANSIFeatures(show_cursor=True)
    HIDE_CURSOR = ANSIFeatures(show_cursor=False)
    ENABLE_ALTERNATE_SCREEN = ANSIFeatures(alternate_screen=True)
    DISABLE_ALTERNATE_SCREEN = ANSIFeatures(alternate_screen=False)
    ENABLE_BRACKETED_PASTE = ANSIFeatures(bracketed_paste=True)
    DISABLE_BRACKETED_PASTE = ANSIFeatures(bracketed_paste=False)
    ENABLE_CURSOR_BLINK = ANSIFeatures(cursor_blink=True)
    DISABLE_CURSOR_BLINK = ANSIFeatures(cursor_blink=False)
    ENABLE_CURSOR_KEYS_APPLICATION_MODE = ANSIFeatures(cursor_keys=True)
    DISABLE_CURSOR_KEYS_APPLICATION_MODE = ANSIFeatures(cursor_keys=False)
    ENABLE_REPLACE_MODE = ANSIFeatures(replace_mode=True)
    DISABLE_REPLACE_MODE = ANSIFeatures(replace_mode=False)
    ENABLE_AUTO_WRAP = ANSIFeatures(auto_wrap=True)
    DISABLE_AUTO_WRAP = ANSIFeatures(auto_wrap=False)

    INVOKE_G2_INTO_GL = DECInvoke(gl=2)
    INVOKE_G3_INTO_GL = DECInvoke(gl=3)
    INVOKE_G1_INTO_GR = DECInvoke(gr=1)
    INVOKE_G2_INTO_GR = DECInvoke(gr=2)
    INVOKE_G3_INTO_GR = DECInvoke(gr=3)
    SHIFT_G2 = DECInvoke(shift=2)
    SHIFT_G3 = DECInvoke(shift=3)

    DEC_INVOKE_MAP = {
        "n": INVOKE_G2_INTO_GL,
        "o": INVOKE_G3_INTO_GL,
        "~": INVOKE_G1_INTO_GR,
        "}": INVOKE_G2_INTO_GR,
        "|": INVOKE_G3_INTO_GR,
        "N": SHIFT_G2,
        "O": SHIFT_G3,
    }

    @classmethod
    @lru_cache(maxsize=1024)
    def _parse_csi(cls, csi: str) -> ANSICommand | None:
        """Parse CSI sequence in to an ansi segment.

        Args:
            csi: CSI sequence.

        Returns:
            Ansi segment, or `None` if one couldn't be decoded.
        """

        if match := re.fullmatch(r"\[(\d+)?(?:;)?(\d*)?(\w)", csi):
            match_groups = match.groups(default="")
            match match_groups:
                case [lines, _, "A"]:
                    # CUU - Cursor Up: ESC[nA
                    return ANSICursor(delta_y=-int(lines or 1))
                case [lines, _, "B"]:
                    # CUD - Cursor Down: ESC[nB
                    return ANSICursor(delta_y=+int(lines or 1))
                case [cells, _, "C"]:
                    # CUF - Cursor Forward: ESC[nC
                    return ANSICursor(delta_x=+int(cells or 1))
                case [cells, _, "D"]:
                    # CUB - Cursor Back: ESC[nD
                    return ANSICursor(delta_x=-int(cells or 1))
                case [lines, _, "E"]:
                    # CNL - Cursor Next Line: ESC[nE
                    return ANSICursor(absolute_x=0, delta_y=+int(lines or 1))
                case [lines, _, "F"]:
                    # CPL - Cursor Previous Line: ESC[nF
                    return ANSICursor(absolute_x=0, delta_y=-int(lines or 1))
                case [cells, _, "G"]:
                    # CHA - Cursor Horizontal Absolute: ESC[nG
                    return ANSICursor(absolute_x=+int(cells or 1) - 1)
                case [row, column, "H" | "f"]:
                    # CUP - Cursor Position: ESC[n;mH
                    # HVP - Horizontal Vertical Position: ESC[n;mf
                    return ANSICursor(
                        absolute_x=int(column or 1) - 1,
                        absolute_y=int(row or 1) - 1,
                    )
                case [characters, _, "P"]:
                    return ANSICursor(
                        clear_range=(0, int(characters or 1) - 1),
                        relative=True,
                        erase=True,
                    )
                case [lines, _, "S"]:
                    return ANSIScroll(-1, int(lines))
                case [lines, _, "T"]:
                    return ANSIScroll(+1, int(lines))
                case [row, _, "d"]:
                    # VPA - Vertical Position Absolute: ESC[nd
                    return ANSICursor(absolute_y=int(row or 1) - 1)
                case [characters, _, "X"]:
                    return ANSICursor(
                        clear_range=(0, int(characters or 1) - 1),
                        relative=True,
                        erase=False,
                    )
                case ["0" | "", _, "J"]:
                    return cls.CLEAR_SCREEN_CURSOR_TO_END
                case ["1", _, "J"]:
                    return cls.CLEAR_SCREEN_CURSOR_TO_BEGINNING
                case ["2", _, "J"]:
                    return cls.CLEAR_SCREEN
                case ["3", _, "J"]:
                    return cls.CLEAR_SCREEN_SCROLLBACK
                case ["0" | "", _, "K"]:
                    return cls.CLEAR_LINE_CURSOR_TO_END
                case ["1", _, "K"]:
                    return cls.CLEAR_LINE_CURSOR_TO_BEGINNING
                case ["2", _, "K"]:
                    return cls.CLEAR_LINE
                case [top, bottom, "r"]:
                    return ANSIScrollMargin(
                        int(top or "1") - 1 if top else None,
                        int(bottom or "1") - 1 if top else None,
                    )
                case ["4", _, "h" | "l" as replace_mode]:
                    return (
                        cls.ENABLE_REPLACE_MODE
                        if replace_mode == "h"
                        else cls.DISABLE_REPLACE_MODE
                    )

                case ["6", _, "n"]:
                    print("CPR")

                case _:
                    print("Unknown CSI (a)", repr(csi))
                    return None

        elif match := re.fullmatch(r"\[([0-9:;<=>?]*)([!-/]*)([@-~])", csi):
            match match.groups(default=""):
                case ["?25", "", "h"]:
                    return cls.SHOW_CURSOR
                case ["?25", "", "l"]:
                    return cls.HIDE_CURSOR
                case ["?1049", "", "h"]:
                    return cls.ENABLE_ALTERNATE_SCREEN
                case ["?1049", "", "l"]:
                    return cls.DISABLE_ALTERNATE_SCREEN
                case ["?2004", "", "h"]:
                    return cls.ENABLE_BRACKETED_PASTE
                case ["?2004", "", "l"]:
                    return cls.DISABLE_BRACKETED_PASTE
                case ["?12", "", "h"]:
                    return cls.ENABLE_CURSOR_BLINK
                case ["?12", "", "l"]:
                    return cls.DISABLE_CURSOR_BLINK
                case ["?1", "", "h"]:
                    return cls.ENABLE_CURSOR_KEYS_APPLICATION_MODE
                case ["?1", "", "l"]:
                    return cls.DISABLE_CURSOR_KEYS_APPLICATION_MODE
                case ["?7", "", "h"]:
                    return cls.ENABLE_AUTO_WRAP
                case ["?7", "", "l"]:
                    return cls.DISABLE_AUTO_WRAP

                # \x1b[22;0;0t
                case [param1, param2, "t"]:
                    print("TODO", "XTWINOPS", param1, param2)
                    # 't' = XTWINOPS (Window manipulation)
                    return None
                case _:
                    if match := re.fullmatch(r"\[\?([0-9;]+)([hl])", csi):
                        modes = [m for m in match.group(1).split(";")]
                        enable = match.group(2) == "h"
                        tracking: Literal["none"] | MOUSE_TRACKING_MODES | None = None
                        format: MOUSE_FORMAT | None = None
                        focus_events: bool | None = None
                        alternate_scroll: bool | None = None
                        for mode in modes:
                            if mode == "1000":
                                tracking = "button" if enable else "none"
                            elif mode == "1002":
                                tracking = "drag" if enable else "none"
                            elif mode == "1003":
                                tracking = "all" if enable else "none"
                            elif mode == "1006":
                                format = "sgr"
                            elif mode == "1015":
                                format = "urxvt"
                            elif mode == "1004":
                                focus_events = enable
                            elif mode == "1007":
                                alternate_scroll = enable
                        return ANSIMouseTracking(
                            mode=tracking,
                            format=format,
                            focus_events=focus_events,
                            alternate_scroll=alternate_scroll,
                        )
                    else:
                        print("Unknown CSI (b)", repr(csi))
                        return None

        if csi == "[6n":
            return ANSICursorPositionRequest()
        print("Unknown CSI (c)", repr(csi))
        return None

    def on_token(self, token: tuple[str, str]) -> Iterable[ANSICommand]:
        match token:
            case ["separator", separator]:
                if separator == "\n":
                    yield ANSINewLine()
                else:
                    yield self.ANSI_SEPARATORS[separator]

            case ["osc", osc]:
                match osc[1:].split(";"):
                    case ["8", *_, link]:
                        self.style += Style(link=link or None)
                    case ["2025", current_directory, *_]:
                        self.current_directory = current_directory
                        yield ANSIWorkingDirectory(current_directory)

            case ["csi", csi]:
                if csi.endswith("m"):
                    if (sgr_style := self._parse_sgr(csi[1:-1])) is None:
                        self.style = NULL_STYLE
                    else:
                        self.style += sgr_style
                        # Special case to use widget background rather
                        # than theme background
                        if (
                            sgr_style.background is not None
                            and sgr_style.background.ansi == -1
                        ):
                            self.style = (
                                Style(foreground=self.style.foreground)
                                + sgr_style.without_color
                            )
                    yield ANSIStyle(self.style)
                else:
                    if (ansi_segment := self._parse_csi(csi)) is not None:
                        yield ansi_segment

            case ["dec", dec]:
                slot, character_set = list(dec)
                yield ANSICharacterSet(DEC(DEC_SLOTS[slot], character_set))

            case ["dec_invoke", dec_invoke]:
                yield ANSICharacterSet(dec_invoke=self.DEC_INVOKE_MAP[dec_invoke[0]])

            case ["control", code]:
                if (control := CONTROL_CODES.get(code)) is not None:
                    if control == "ri":  # control code
                        yield ANSICursor(delta_y=-1, auto_scroll=True)
                    elif control == "ind":
                        yield ANSICursor(delta_y=+1, auto_scroll=True)
                    else:
                        print("CONTROL", repr(code), repr(control))
                else:
                    print("NOT HANDLED", code)

            case ["content", text]:
                yield ANSIContent(text)

            case _:
                print("UNKNWON TOKEN", repr(token))


class LineFold(NamedTuple):
    """A line from the terminal, folded for presentation."""

    line_no: int
    """The (unfolded) line number."""

    line_offset: int
    """The index of the folded line."""

    offset: int
    """The offset within the original line."""

    content: Content
    """The content."""

    updates: int = 0
    """Integer that increments on update."""


@dataclass
class LineRecord:
    """A single line in the terminal."""

    content: Content
    """The content."""

    style: Style = NULL_STYLE
    """The style for the remaining line."""

    folds: list[LineFold] = field(default_factory=list)
    """Line "folds" for wrapped lines."""

    updates: int = 0
    """An integer used for caching."""


@rich.repr.auto
class ScrollMargin(NamedTuple):
    """Margins at the top and bottom of a window that won't scroll."""

    top: int | None = None
    """Margin at the top (in lines), or `None` for no scroll margin set."""
    bottom: int | None = None
    """Margin at the bottom (in lines), or `None` for no scroll margin set."""

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.top
        yield self.bottom

    def get_line_range(self, height: int) -> tuple[int, int]:
        """Get the scrollable line range (inclusive).

        Args:
            height: terminal height.

        Returns:
            A tuple of the (exclusive) top and bottom line numbers that scroll.
        """
        return (
            self.top or 0,
            height - 1 if self.bottom is None else self.bottom,
        )


@dataclass
class Buffer:
    """A terminal buffer (scrollback or alternate)"""

    name: str = "buffer"
    """Name of the buffer (debugging aid)."""
    lines: list[LineRecord] = field(default_factory=list)
    """unfolded lines."""
    line_to_fold: list[int] = field(default_factory=list)
    """An index from folded lines on to unfolded lines."""
    folded_lines: list[LineFold] = field(default_factory=list)
    """Folded lines."""
    scroll_margin: ScrollMargin = ScrollMargin(None, None)
    """Scroll margins"""
    cursor_line: int = 0
    """Folded line index."""
    cursor_offset: int = 0
    """Folded line offset."""
    max_line_width: int = 0
    """The longest line in the buffer."""
    updates: int = 0
    """Updates count (used in caching)."""
    _updated_lines: set[int] | None = None

    @property
    def line_count(self) -> int:
        """Total number of lines."""
        return len(self.lines)

    @property
    def height(self) -> int:
        """Height of the buffer (number of folded lines)."""
        return len(self.folded_lines)

    @property
    def last_line_no(self) -> int:
        """Index of last lines."""
        return len(self.lines) - 1

    @property
    def unfolded_line(self) -> int:
        """THh unfolded line index under the cursor."""
        cursor_folded_line = self.folded_lines[self.cursor_line]
        return cursor_folded_line.line_no

    @property
    def cursor(self) -> tuple[int, int]:
        """The cursor offset within the un-folded lines."""

        if self.cursor_line >= len(self.folded_lines):
            return (len(self.folded_lines), 0)
        cursor_folded_line = self.folded_lines[self.cursor_line]
        cursor_line_offset = cursor_folded_line.line_offset
        line_no = cursor_folded_line.line_no
        line = self.lines[line_no]
        position = 0
        for folded_line_offset, folded_line in enumerate(line.folds):
            if folded_line_offset == cursor_line_offset:
                position += self.cursor_offset
                break
            position += len(folded_line.content)

        return (line_no, position)

    @property
    def is_blank(self) -> bool:
        """Is this buffer blank (spaces in all lines)?"""
        return not any(line.content.plain.strip() for line in self.lines)

    def update_cursor(self, line_no: int, cursor_line_offset: int) -> None:
        """Move the cursor to the given unfolded line and offset.

        Sets `cursor_line` and `cursor_offset`.

        Args:
            line_no: Unfolded line number.
            cursor_line_offset: Offset within the line.
        """
        line = self.lines[line_no]
        fold_line_start = self.line_to_fold[line_no]
        position = 0
        fold_offset = 0
        for fold_offset, fold in enumerate(line.folds):
            line_length = len(fold.content)
            if (
                cursor_line_offset >= position
                and cursor_line_offset < position + line_length
            ):
                self.cursor_line = fold_line_start + fold_offset
                self.cursor_offset = cursor_line_offset - position
                break
            position += line_length
        else:
            self.cursor_line = fold_line_start + len(line.folds) - 1
            self.cursor_offset = len(line.folds[-1].content)

    def update_line(self, line_no: int) -> None:
        """Record an updated line.

        Args:
            line_no: Line number to update.
        """
        if self._updated_lines is not None:
            self._updated_lines.add(line_no)

    def clear(self, updates: int) -> None:
        """Clear the buffer to its initial state.

        Args:
            updates: the initial updates index.

        """
        del self.lines[:]
        del self.line_to_fold[:]
        del self.folded_lines[:]
        self.cursor_line = 0
        self.cursor_offset = 0
        self.max_line_width = 0
        self.updates = updates


@dataclass
class DECState:
    """The (somewhat bonkers) mechanism for switching characters sets pre-unicode."""

    slots: list[str] = field(default_factory=lambda: ["B", "B", "<", "0"])
    gl_slot: int = 0
    gr_slot: int = 2
    shift: int | None = None

    @property
    def gl(self) -> str:
        return self.slots[self.gl_slot]

    @property
    def gr(self) -> str:
        return self.slots[self.gr_slot]

    def update(self, dec: DEC | None, dec_invoke: DECInvoke | None) -> None:
        if dec is not None:
            self.slots[dec.slot] = dec.character_set
        elif dec_invoke is not None:
            if dec_invoke.shift:
                self.shift = dec_invoke.shift
            else:
                if dec_invoke.gl is not None:
                    self.gl_slot = dec_invoke.gl
                elif dec_invoke.gr is not None:
                    self.gr_slot = dec_invoke.gr

    def translate(self, text: str) -> str:
        translate_table: dict[int, str] | None
        first_character: str | None = None
        if self.shift is not None and (
            translate_table := CHARSET_MAP.get(self.slots[self.shift], None)
        ):
            first_character = text[0].translate(translate_table)
            self.shift = None

        if translate_table := CHARSET_MAP.get(self.gl, None):
            text = text.translate(translate_table)
        if first_character is None:
            return text
        return f"{first_character}{text}"


@dataclass
class MouseTracking:
    """The mouse tracking state."""

    tracking: MOUSE_TRACKING_MODES = "all"
    format: MOUSE_FORMAT = "normal"
    focus_events: bool = False
    alternate_scroll: bool = False


@rich.repr.auto
class TerminalState:
    """Abstract terminal state."""

    def __init__(
        self, write_stdin: Callable[[str], Any], *, width: int = 80, height: int = 24
    ) -> None:
        """
        Args:
            width: Initial width.
            height: Initial height.
        """
        self._write_stdin: Callable[[str], Any] | None = write_stdin

        self._ansi_stream = ANSIStream()
        """ANSI stream processor."""

        self.width = width
        """Width of the terminal."""
        self.height = height
        """Height of the terminal."""
        self.style = NULL_STYLE
        """The current style."""
        self.show_cursor = True
        """Is the cursor visible?"""
        self.alternate_screen = False
        """Is the terminal in the alternate buffer state?"""
        self.bracketed_paste = False
        """Is bracketed pase enabled?"""
        self.cursor_blink = False
        """Should the cursor blink?"""
        self.cursor_keys = False
        """Is cursor keys application mode enabled?"""
        self.replace_mode = True
        """Should content replaces characters (`True`) or insert (`False`)?"""
        self.auto_wrap = True
        """Should content wrap?"""
        self.current_directory: str = ""
        """Current working directory."""
        self.scrollback_buffer = Buffer("scrollback")
        """Scrollbar buffer lines."""
        self.alternate_buffer = Buffer("alternate")
        """Alternate buffer lines."""
        self.dec_state = DECState()
        """The DEC (character set) state."""
        self.mouse_tracking: MouseTracking | None = None
        """The mouse tracking state."""

        self._updates: int = 0
        """Incrementing integer used in caching."""

    def __rich_repr__(self) -> rich.repr.Result:
        yield "width", self.width
        yield "height", self.height
        yield "style", self.style, NULL_STYLE
        yield "show_cursor", self.show_cursor, True
        yield "alternate_screen", self.alternate_screen, False
        yield "bracketed_paste", self.bracketed_paste, False
        yield "cursor_blink", self.cursor_blink, False
        yield "replace_mode", self.replace_mode, True
        yield "auto_wrap", self.auto_wrap, True
        yield "dec_state", self.dec_state
        yield "mouse_tracking", self.mouse_tracking, None

    def write_stdin(self, text: str) -> bool:
        if self._write_stdin is not None:
            self._write_stdin(text)
            return False
        return True

    @property
    def screen_start_line_no(self) -> int:
        return self.buffer.line_count - self.height

    @property
    def screen_end_line_no(self) -> int:
        return self.buffer.line_count

    @property
    def updates(self) -> int:
        """An integer that advanvces when the state is changed."""
        return self._updates

    @property
    def buffer(self) -> Buffer:
        """The buffer (scrollack or alternate)"""
        if self.alternate_screen:
            return self.alternate_buffer
        return self.scrollback_buffer

    @property
    def max_line_width(self) -> int | None:
        return self.scrollback_buffer.max_line_width

    def advance_updates(self) -> int:
        """Advance the `updates` integer and return it.

        Returns:
            int: Updates.
        """
        self._updates += 1
        return self._updates

    def update_size(self, width: int | None = None, height: int | None = None) -> None:
        """Update the dimensions of the terminal.

        Args:
            width: New width, or `None` for no change.
            height: New height, or `None` for no change.
        """
        previous_width = self.width
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height

        if previous_width != width:
            self._reflow()

    def key_event_to_stdin(self, event: events.Key) -> str | None:
        """Get the stdin string for a key event.

        This will depend on the terminal state.

        Args:
            event: Key event.

        Returns:
            A string to be sent to stdin, or `None` if no key was produced.
        """
        if (
            self.cursor_keys
            and (sequence := CURSOR_KEYS_APPLICATION.get(event.key)) is not None
        ):
            return sequence

        if (mapped_key := TERMINAL_KEY_MAP.get(event.key)) is not None:
            return mapped_key
        if event.character:
            return event.character
        return None

    def key_escape(self) -> str:
        """Generate the escape sequence for the escape key.

        Returns:
            str: ANSI escape sequences.
        """
        return "\x1b"

    def _reflow(self) -> None:
        buffer = self.buffer
        if not buffer.lines:
            return

        buffer._updated_lines = None
        # Unfolded cursor position
        cursor_line, cursor_offset = buffer.cursor

        buffer.folded_lines.clear()
        buffer.line_to_fold.clear()
        width = self.width

        for line_no, line_record in enumerate(buffer.lines):
            line_expanded_tabs = line_record.content.expand_tabs(8)
            line_record.folds[:] = self._fold_line(line_no, line_expanded_tabs, width)
            line_record.updates = self.advance_updates()
            buffer.line_to_fold.append(len(buffer.folded_lines))
            buffer.folded_lines.extend(line_record.folds)

        # After reflow, we need to work out where the cursor is within the folded lines
        # cursor_line = min(cursor_line, len(buffer.lines) - 1)
        if cursor_line >= len(buffer.lines):
            buffer.cursor_line = len(buffer.lines)
            buffer.cursor_offset = 0
        else:
            line = buffer.lines[cursor_line]
            fold_cursor_line = buffer.line_to_fold[cursor_line]

            fold_cursor_offset = 0
            for fold in reversed(line.folds):
                if cursor_offset >= fold.offset:
                    fold_cursor_line += fold.line_offset
                    fold_cursor_offset = cursor_offset - fold.offset
                    break

            buffer.cursor_line = fold_cursor_line
            buffer.cursor_offset = fold_cursor_offset

    def write(self, text: str) -> tuple[set[int] | None, set[int] | None]:
        """Write to the terminal.

        Args:
            text: Text to write.

        Returns:
            A pair of deltas or `None for full refresh, for scrollback and alternate screen.
        """

        alternate_buffer = self.alternate_buffer
        scrollback_buffer = self.scrollback_buffer

        # Reset updated lines delta
        alternate_buffer._updated_lines = set()
        scrollback_buffer._updated_lines = set()
        # Write sequences and update
        for ansi_command in self._ansi_stream.feed(text):
            self._handle_ansi_command(ansi_command)

        # Get deltas
        scrollback_updates = (
            None
            if scrollback_buffer._updated_lines is None
            else scrollback_buffer._updated_lines.copy()
        )
        alternate_updates = (
            None
            if alternate_buffer._updated_lines is None
            else alternate_buffer._updated_lines.copy()
        )
        # Reset deltas
        self.alternate_buffer._updated_lines = set()
        self.scrollback_buffer._updated_lines = set()
        # Return deltas accumulated during write
        return (scrollback_updates, alternate_updates)

    def get_cursor_line_offset(self, buffer: Buffer) -> int:
        """The cursor offset within the un-folded lines."""
        cursor_folded_line = buffer.folded_lines[buffer.cursor_line]
        cursor_line_offset = cursor_folded_line.line_offset
        line_no = cursor_folded_line.line_no
        line = buffer.lines[line_no]
        position = 0
        for folded_line_offset, folded_line in enumerate(line.folds):
            if folded_line_offset == cursor_line_offset:
                position += buffer.cursor_offset
                break
            position += len(folded_line.content)
        return position

    def clear_buffer(self, clear: ClearType) -> None:
        buffer = self.buffer
        if clear == "screen":
            buffer.clear(self.advance_updates())
            # for _ in range(self.height):
            #     self.add_line(buffer, EMPTY_CONTENT)
        elif clear == "cursor_to_end":
            buffer._updated_lines = None
            folded_cursor_line = buffer.cursor_line
            cursor_line, cursor_line_offset = buffer.cursor
            while buffer.cursor_line >= len(buffer.folded_lines):
                self.add_line(buffer, EMPTY_LINE)
            line = buffer.lines[cursor_line]
            del buffer.lines[cursor_line + 1 :]
            del buffer.line_to_fold[cursor_line + 1 :]
            del buffer.folded_lines[folded_cursor_line + 1 :]
            self.update_line(buffer, cursor_line, line.content[:cursor_line_offset])
        else:
            # print(f"TODO: clear_buffer({clear!r})")
            buffer.clear(self.advance_updates())

    def scroll_buffer(self, direction: int, lines: int) -> None:
        """Scroll the buffer.

        Args:
            direction: +1 for down, -1 for up.
            lines: Number of lines.
        """
        buffer = self.buffer
        margin_top, margin_bottom = buffer.scroll_margin.get_line_range(self.height)

        if direction == -1:
            # up (first in test)
            for line_no in range(margin_top, margin_bottom + 1):
                copy_line_no = line_no + lines
                copy_content = EMPTY_CONTENT
                copy_style = NULL_STYLE
                if copy_line_no <= margin_bottom:
                    try:
                        copy_line = buffer.lines[copy_line_no]
                    except IndexError:
                        pass
                    else:
                        copy_content = copy_line.content
                        copy_style = copy_line.style

                self.update_line(buffer, line_no, copy_content, copy_style)
        else:
            # down
            for line_no in reversed(range(margin_top, margin_bottom + 1)):
                copy_line_no = line_no - lines
                copy_content = EMPTY_CONTENT
                copy_style = NULL_STYLE
                if copy_line_no >= margin_top:
                    try:
                        copy_line = buffer.lines[copy_line_no]
                    except IndexError:
                        pass
                    else:
                        copy_content = copy_line.content
                        copy_style = copy_line.style
                self.update_line(buffer, line_no, copy_content, copy_style)

    @classmethod
    def _expand_content(cls, content: Content, offset: int, style: Style) -> Content:
        """Expand content to be at least as long as a given offset.

        Args:
            content: Content to expand.
            offset: Offset within the content.
            style: Style of padding.

        Returns:
            New Content.
        """
        if offset > len(content):
            content += Content.blank(offset - len(content), style)
        return content

    def _handle_ansi_command(self, ansi_command: ANSICommand) -> None:
        if isinstance(ansi_command, ANSINewLine):
            if self.alternate_screen:
                # New line behaves differently in alternate screen
                ansi_command = ANSICursor(delta_y=+1, auto_scroll=True)
            else:
                ansi_command = ANSICursor(delta_y=+1, absolute_x=0)

        match ansi_command:
            case ANSIStyle(style):
                self.style = style

            case ANSIContent(text):
                buffer = self.buffer
                folded_lines = buffer.folded_lines
                while buffer.cursor_line >= len(folded_lines):
                    self.add_line(buffer, EMPTY_LINE)
                folded_line = folded_lines[buffer.cursor_line]
                previous_content = folded_line.content
                line_no = folded_line.line_no
                line = buffer.lines[line_no]

                cursor_line_offset = self.get_cursor_line_offset(buffer)
                line_content = line.content
                if cursor_line_offset > len(line_content):
                    line_content = self._expand_content(
                        line_content, cursor_line_offset, line.style
                    )
                content = Content.styled(
                    self.dec_state.translate(text),
                    self.style,
                    strip_control_codes=False,
                )
                if self.replace_mode:
                    updated_line = Content.assemble(
                        line_content[:cursor_line_offset],
                        content,
                        line_content[cursor_line_offset + len(content) :],
                        strip_control_codes=False,
                    )
                else:
                    updated_line = Content.assemble(
                        line_content[:cursor_line_offset],
                        content,
                        line_content[cursor_line_offset:],
                        strip_control_codes=False,
                    )
                self.update_line(buffer, line_no, updated_line)
                buffer.update_cursor(line_no, cursor_line_offset + len(content))
                buffer.updates = self.advance_updates()

            case ANSICursor(
                delta_x,
                delta_y,
                absolute_x,
                absolute_y,
                erase,
                clear_range,
                _relative,
                update_background,
                auto_scroll,
            ):
                # print(repr(ansi_command))
                buffer = self.buffer
                folded_lines = buffer.folded_lines
                while buffer.cursor_line >= len(folded_lines):
                    self.add_line(buffer, EMPTY_LINE)

                if auto_scroll and delta_y is not None:
                    margins = buffer.scroll_margin.get_line_range(self.height)
                    margin_top, margin_bottom = margins

                    if (
                        buffer.cursor_line >= margin_top
                        and buffer.cursor_line <= margin_bottom
                    ):
                        start_line_no = self.screen_start_line_no
                        start_line_no = 0
                        scroll_cursor = buffer.cursor_line + delta_y
                        if scroll_cursor > (start_line_no + margin_bottom):
                            self.scroll_buffer(-1, 1)
                            return
                        elif scroll_cursor < (start_line_no + margin_top):
                            self.scroll_buffer(+1, 1)
                            return

                folded_line = folded_lines[buffer.cursor_line]
                previous_content = folded_line.content
                line = buffer.lines[folded_line.line_no]
                if update_background:
                    line.style = self.style

                if clear_range is not None:
                    cursor_line_offset = self.get_cursor_line_offset(buffer)

                    line_content = line.content
                    if cursor_line_offset > len(line.content):
                        line_content = self._expand_content(
                            line.content, cursor_line_offset, line.style
                        )

                    # Start and end replace are *inclusive*
                    clear_start, clear_end = ansi_command.get_clear_offsets(
                        cursor_line_offset, len(line_content)
                    )

                    before_clear = line_content[:clear_start]
                    after_clear = line_content[clear_end + 1 :]

                    if erase:
                        # Range is remove
                        updated_line = Content.assemble(
                            before_clear,
                            after_clear,
                            strip_control_codes=False,
                        )
                        self.update_line(buffer, folded_line.line_no, updated_line)
                    else:
                        # Range is replaced with spaces
                        blank_width = clear_end - clear_start + 1

                        updated_line = Content.assemble(
                            before_clear,
                            Content.blank(blank_width, self.style),
                            after_clear,
                            strip_control_codes=False,
                        )
                        self.update_line(buffer, folded_line.line_no, updated_line)

                if not previous_content.is_same(folded_line.content):
                    buffer.updates = self.advance_updates()

                if delta_x is not None:
                    buffer.cursor_offset = clamp(
                        buffer.cursor_offset + delta_x, 0, self.width - 1
                    )
                    buffer.update_line(buffer.cursor_line)
                if absolute_x is not None:
                    buffer.cursor_offset = clamp(absolute_x, 0, self.width - 1)
                    buffer.update_line(buffer.cursor_line)

                current_cursor_line = buffer.cursor_line
                if delta_y is not None:
                    buffer.update_line(buffer.cursor_line)
                    buffer.cursor_line = max(0, buffer.cursor_line + delta_y)
                    buffer.update_line(buffer.cursor_line)
                if absolute_y is not None:
                    buffer.update_line(buffer.cursor_line)
                    buffer.cursor_line = max(0, absolute_y)
                    buffer.update_line(buffer.cursor_line)

                if current_cursor_line != buffer.cursor_line:
                    # Simplify when the cursor moves away from the current line
                    line.content.simplify()  # Reduce segments
                    self._line_updated(buffer, current_cursor_line)
                    self._line_updated(buffer, buffer.cursor_line)

            case ANSIFeatures() as features:
                if features.show_cursor is not None:
                    self.show_cursor = features.show_cursor
                if features.alternate_screen is not None:
                    self.alternate_screen = features.alternate_screen
                if features.bracketed_paste is not None:
                    self.bracketed_paste = features.bracketed_paste
                if features.cursor_blink is not None:
                    self.cursor_blink = features.cursor_blink
                if features.cursor_keys is not None:
                    self.cursor_keys = features.cursor_keys
                if features.auto_wrap is not None:
                    self.auto_wrap = features.auto_wrap
                self.advance_updates()

            case ANSIClear(clear):
                self.clear_buffer(clear)

            case ANSIScrollMargin(top, bottom):
                self.buffer.scroll_margin = ScrollMargin(top, bottom)
                # Setting the scroll margins moves the cursor to (1, 1)
                buffer = self.buffer
                self._line_updated(buffer, buffer.cursor_line)
                buffer.cursor_line = 0
                buffer.cursor_offset = 0
                self._line_updated(buffer, buffer.cursor_line)

            case ANSIScroll(direction, lines):
                self.scroll_buffer(direction, lines)

            case ANSICharacterSet(dec, dec_invoke):
                self.dec_state.update(dec, dec_invoke)

            case ANSIWorkingDirectory(path):
                self.current_directory = path

            case ANSIMouseTracking(tracking, format, focus_events, alternate_scroll):
                if tracking == "none":
                    self.mouse_tracking = None
                    return
                if (mouse_tracking := self.mouse_tracking) is None:
                    mouse_tracking = self.mouse_tracking = MouseTracking()
                if tracking is not None:
                    mouse_tracking.tracking = tracking
                if format is not None:
                    mouse_tracking.format = format
                if focus_events is not None:
                    mouse_tracking.focus_events = focus_events
                if alternate_scroll is not None:
                    mouse_tracking.alternate_scroll = alternate_scroll

            case ANSICursorPositionRequest():
                row = self.buffer.cursor_line + 1
                column = self.buffer.cursor_offset + 1
                self.write_stdin(f"[{row};{column}R")

            case _:
                print("Unhandled", ansi_command)

    def _line_updated(self, buffer: Buffer, line_no: int) -> None:
        """Mark a line has having been udpated.

        Args:
            buffer: Buffer to use.
            line_no: Line number to mark as updated.
        """
        try:
            buffer.lines[line_no].updates = self.advance_updates()
            if buffer._updated_lines is not None:
                buffer._updated_lines.add(line_no)
        except IndexError:
            pass

    def _fold_line(self, line_no: int, line: Content, width: int) -> list[LineFold]:
        updates = self._updates
        if not self.auto_wrap:
            return [LineFold(line_no, 0, 0, line, updates)]
        if not width:
            return [LineFold(0, 0, 0, line, updates)]
        line_length = line.cell_length
        if line_length <= width:
            return [LineFold(line_no, 0, 0, line, updates)]

        folded_lines = line.fold(width)
        offsets = [0, *accumulate(len(line) for line in folded_lines)][:-1]
        folds = [
            LineFold(line_no, line_offset, offset, folded_line, updates)
            for line_offset, (offset, folded_line) in enumerate(
                zip(offsets, folded_lines)
            )
        ]
        assert len(folds)
        return folds

    def add_line(
        self, buffer: Buffer, content: Content, style: Style = NULL_STYLE
    ) -> None:
        updates = self.advance_updates()
        line_no = buffer.line_count
        width = self.width
        line_record = LineRecord(
            content,
            style,
            self._fold_line(line_no, content, width),
            updates,
        )
        buffer.lines.append(line_record)
        folds = line_record.folds
        buffer.line_to_fold.append(len(buffer.folded_lines))
        fold_count = len(buffer.folded_lines)
        if buffer._updated_lines is not None:
            buffer._updated_lines.update(range(fold_count, fold_count + len(folds)))
        buffer.folded_lines.extend(folds)
        buffer.updates = updates

    def update_line(
        self, buffer: Buffer, line_index: int, line: Content, style: Style | None = None
    ) -> None:
        """Update a line (potentially refolding and moving subsequencte lines down).

        Args:
            buffer: Buffer.
            line_index: Line index (unfolded).
            line: New line content.
            style: New background style, or `None` not to update.
        """
        while line_index >= len(buffer.lines):
            self.add_line(buffer, EMPTY_LINE)

        line_expanded_tabs = line.expand_tabs(8)
        buffer.max_line_width = max(
            line_expanded_tabs.cell_length, buffer.max_line_width
        )
        line_record = buffer.lines[line_index]
        line_record.content = line
        if style is not None:
            line_record.style = style
        line_record.folds[:] = self._fold_line(
            line_index, line_expanded_tabs, self.width
        )
        line_record.updates = self.advance_updates()

        if buffer._updated_lines is not None:
            fold_start = buffer.line_to_fold[line_index]
            buffer._updated_lines.update(
                range(fold_start, fold_start + len(line_record.folds))
            )

        fold_line = buffer.line_to_fold[line_index]
        del buffer.line_to_fold[line_index:]
        del buffer.folded_lines[fold_line:]

        for line_no in range(line_index, buffer.line_count):
            line_record = buffer.lines[line_no]
            buffer.line_to_fold.append(len(buffer.folded_lines))
            for fold in line_record.folds:
                buffer.folded_lines.append(fold)
