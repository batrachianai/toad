from __future__ import annotations

import rich.repr

import re
from dataclasses import dataclass
from functools import lru_cache
import io

from typing import Iterable, Mapping, NamedTuple, Sequence
from textual.color import Color
from textual.style import Style, NULL_STYLE
from textual.content import Content, EMPTY_CONTENT

from toad._stream_parser import (
    MatchToken,
    StreamParser,
    SeparatorToken,
    PatternToken,
    Pattern,
    PatternCheck,
    ParseResult,
)


def as_int(text: str) -> int:
    """Convert a string to an integer, or return `0` if conversion is impossible"""
    if not text.isdecimal():
        return 0
    try:
        return int(text)
    except ValueError:
        return 0


class CSIPattern(Pattern):
    """Control Sequence Introducer."""

    PARAMETER_BYTES = frozenset([chr(codepoint) for codepoint in range(0x30, 0x3F + 1)])
    INTERMEDIATE_BYTES = frozenset(
        [chr(codepoint) for codepoint in range(0x20, 0x2F + 1)]
    )
    FINAL_BYTE = frozenset([chr(codepoint) for codepoint in range(0x40, 0x7E + 1)])

    class Match(NamedTuple):
        parameter: str
        intermediate: str
        final: str

        @property
        def full(self) -> str:
            return f"\x1b[{self.parameter}{self.intermediate}{self.final}"

    def check(self) -> PatternCheck:
        """Check a CSI pattern."""
        if (yield) != "[":
            return False

        parameter = io.StringIO()
        intermediate = io.StringIO()
        parameter_bytes = self.PARAMETER_BYTES

        while (character := (yield)) in parameter_bytes:
            parameter.write(character)

        if character in self.FINAL_BYTE:
            return self.Match(parameter.getvalue(), "", character)

        intermediate_bytes = self.INTERMEDIATE_BYTES
        while True:
            intermediate.write(character)
            if (character := (yield)) not in intermediate_bytes:
                break

        final_byte = character
        if final_byte not in self.FINAL_BYTE:
            return False

        return self.Match(
            parameter.getvalue(),
            intermediate.getvalue(),
            final_byte,
        )


class OSCPattern(Pattern):
    class Match(NamedTuple):
        code: str

    def check(self) -> PatternCheck:
        if (yield) != "]":
            return False
        return self.Match("]")


SGR_STYLE_MAP: Mapping[int, Style] = {
    1: Style(bold=True),
    2: Style(dim=True),
    3: Style(italic=True),
    4: Style(underline=True),
    5: Style(blink=True),
    6: Style(blink=True),
    7: Style(reverse=True),
    8: Style(reverse=True),
    9: Style(strike=True),
    21: Style(underline2=True),
    22: Style(dim=False, bold=False),
    23: Style(italic=False),
    24: Style(underline=False),
    25: Style(blink=False),
    26: Style(blink=False),
    27: Style(reverse=False),
    28: NULL_STYLE,  # "not conceal",
    29: Style(strike=False),
    30: Style(foreground=Color(0, 0, 0, ansi=0)),
    31: Style(foreground=Color(128, 0, 0, ansi=1)),
    32: Style(foreground=Color(0, 128, 0, ansi=2)),
    33: Style(foreground=Color(128, 128, 0, ansi=3)),
    34: Style(foreground=Color(0, 0, 128, ansi=4)),
    35: Style(foreground=Color(128, 0, 128, ansi=5)),
    36: Style(foreground=Color(0, 128, 128, ansi=6)),
    37: Style(foreground=Color(192, 192, 192, ansi=7)),
    39: Style(foreground=Color(0, 0, 0, ansi=-1)),
    40: Style(background=Color(0, 0, 0, ansi=0)),
    41: Style(background=Color(128, 0, 0, ansi=1)),
    42: Style(background=Color(0, 128, 0, ansi=2)),
    43: Style(background=Color(128, 128, 0, ansi=3)),
    44: Style(background=Color(0, 0, 128, ansi=4)),
    45: Style(background=Color(128, 0, 128, ansi=5)),
    46: Style(background=Color(0, 128, 128, ansi=6)),
    47: Style(background=Color(192, 192, 192, ansi=7)),
    49: Style(background=Color(0, 0, 0, ansi=-1)),
    51: NULL_STYLE,  # "frame",
    52: NULL_STYLE,  # "encircle",
    53: NULL_STYLE,  # "overline",
    54: NULL_STYLE,  # "not frame not encircle",
    55: NULL_STYLE,  # "not overline",
    90: Style(foreground=Color(128, 128, 128, ansi=8)),
    91: Style(foreground=Color(255, 0, 0, ansi=9)),
    92: Style(foreground=Color(0, 255, 0, ansi=10)),
    93: Style(foreground=Color(255, 255, 0, ansi=11)),
    94: Style(foreground=Color(0, 0, 255, ansi=12)),
    95: Style(foreground=Color(255, 0, 255, ansi=13)),
    96: Style(foreground=Color(0, 255, 255, ansi=14)),
    97: Style(foreground=Color(255, 255, 255, ansi=15)),
    100: Style(background=Color(128, 128, 128, ansi=8)),
    101: Style(background=Color(255, 0, 0, ansi=9)),
    102: Style(background=Color(0, 255, 0, ansi=10)),
    103: Style(background=Color(255, 255, 0, ansi=11)),
    104: Style(background=Color(0, 0, 255, ansi=12)),
    105: Style(background=Color(255, 0, 255, ansi=13)),
    106: Style(background=Color(0, 255, 255, ansi=14)),
    107: Style(background=Color(255, 255, 255, ansi=15)),
}


@dataclass
class ANSIToken:
    text: str


class Separator(ANSIToken):
    pass


@dataclass
class CSI(ANSIToken):
    pass


@dataclass
class OSC(ANSIToken):
    pass


class ANSIParser(StreamParser[ANSIToken]):
    def parse(self) -> ParseResult[ANSIToken]:
        NEW_LINE = "\n"
        CARRIAGE_RETURN = "\r"
        ESCAPE = "\x1b"
        BACKSPACE = "\x08"

        while True:
            token = yield self.read_until(NEW_LINE, CARRIAGE_RETURN, ESCAPE, BACKSPACE)

            if isinstance(token, SeparatorToken):
                if token.text == ESCAPE:
                    token = yield self.read_patterns(
                        "\x1b", csi=CSIPattern(), osc=OSCPattern()
                    )

                    if isinstance(token, PatternToken):
                        value = token.value

                        if isinstance(value, CSIPattern.Match):
                            yield CSI(value.full)

                        elif isinstance(value, OSCPattern.Match):
                            osc_data: list[str] = []

                            while not isinstance(
                                token := (yield self.read_regex(r"\x1b\\|\x07")),
                                MatchToken,
                            ):
                                osc_data.append(token.text)
                            yield OSC("".join(osc_data))
                            continue
                else:
                    yield Separator(token.text)
                continue

            yield ANSIToken(token.text)


EMPTY_LINE = Content()


ANSI_COLORS: Sequence[str] = [
    "ansi_black",
    "ansi_red",
    "ansi_green",
    "ansi_yellow",
    "ansi_blue",
    "ansi_magenta",
    "ansi_cyan",
    "ansi_white",
    "ansi_bright_black",
    "ansi_bright_red",
    "ansi_bright_green",
    "ansi_bright_yellow",
    "ansi_bright_blue",
    "ansi_bright_magenta",
    "ansi_bright_cyan",
    "ansi_bright_white",
    "rgb(0,0,0)",
    "rgb(0,0,95)",
    "rgb(0,0,135)",
    "rgb(0,0,175)",
    "rgb(0,0,215)",
    "rgb(0,0,255)",
    "rgb(0,95,0)",
    "rgb(0,95,95)",
    "rgb(0,95,135)",
    "rgb(0,95,175)",
    "rgb(0,95,215)",
    "rgb(0,95,255)",
    "rgb(0,135,0)",
    "rgb(0,135,95)",
    "rgb(0,135,135)",
    "rgb(0,135,175)",
    "rgb(0,135,215)",
    "rgb(0,135,255)",
    "rgb(0,175,0)",
    "rgb(0,175,95)",
    "rgb(0,175,135)",
    "rgb(0,175,175)",
    "rgb(0,175,215)",
    "rgb(0,175,255)",
    "rgb(0,215,0)",
    "rgb(0,215,95)",
    "rgb(0,215,135)",
    "rgb(0,215,175)",
    "rgb(0,215,215)",
    "rgb(0,215,255)",
    "rgb(0,255,0)",
    "rgb(0,255,95)",
    "rgb(0,255,135)",
    "rgb(0,255,175)",
    "rgb(0,255,215)",
    "rgb(0,255,255)",
    "rgb(95,0,0)",
    "rgb(95,0,95)",
    "rgb(95,0,135)",
    "rgb(95,0,175)",
    "rgb(95,0,215)",
    "rgb(95,0,255)",
    "rgb(95,95,0)",
    "rgb(95,95,95)",
    "rgb(95,95,135)",
    "rgb(95,95,175)",
    "rgb(95,95,215)",
    "rgb(95,95,255)",
    "rgb(95,135,0)",
    "rgb(95,135,95)",
    "rgb(95,135,135)",
    "rgb(95,135,175)",
    "rgb(95,135,215)",
    "rgb(95,135,255)",
    "rgb(95,175,0)",
    "rgb(95,175,95)",
    "rgb(95,175,135)",
    "rgb(95,175,175)",
    "rgb(95,175,215)",
    "rgb(95,175,255)",
    "rgb(95,215,0)",
    "rgb(95,215,95)",
    "rgb(95,215,135)",
    "rgb(95,215,175)",
    "rgb(95,215,215)",
    "rgb(95,215,255)",
    "rgb(95,255,0)",
    "rgb(95,255,95)",
    "rgb(95,255,135)",
    "rgb(95,255,175)",
    "rgb(95,255,215)",
    "rgb(95,255,255)",
    "rgb(135,0,0)",
    "rgb(135,0,95)",
    "rgb(135,0,135)",
    "rgb(135,0,175)",
    "rgb(135,0,215)",
    "rgb(135,0,255)",
    "rgb(135,95,0)",
    "rgb(135,95,95)",
    "rgb(135,95,135)",
    "rgb(135,95,175)",
    "rgb(135,95,215)",
    "rgb(135,95,255)",
    "rgb(135,135,0)",
    "rgb(135,135,95)",
    "rgb(135,135,135)",
    "rgb(135,135,175)",
    "rgb(135,135,215)",
    "rgb(135,135,255)",
    "rgb(135,175,0)",
    "rgb(135,175,95)",
    "rgb(135,175,135)",
    "rgb(135,175,175)",
    "rgb(135,175,215)",
    "rgb(135,175,255)",
    "rgb(135,215,0)",
    "rgb(135,215,95)",
    "rgb(135,215,135)",
    "rgb(135,215,175)",
    "rgb(135,215,215)",
    "rgb(135,215,255)",
    "rgb(135,255,0)",
    "rgb(135,255,95)",
    "rgb(135,255,135)",
    "rgb(135,255,175)",
    "rgb(135,255,215)",
    "rgb(135,255,255)",
    "rgb(175,0,0)",
    "rgb(175,0,95)",
    "rgb(175,0,135)",
    "rgb(175,0,175)",
    "rgb(175,0,215)",
    "rgb(175,0,255)",
    "rgb(175,95,0)",
    "rgb(175,95,95)",
    "rgb(175,95,135)",
    "rgb(175,95,175)",
    "rgb(175,95,215)",
    "rgb(175,95,255)",
    "rgb(175,135,0)",
    "rgb(175,135,95)",
    "rgb(175,135,135)",
    "rgb(175,135,175)",
    "rgb(175,135,215)",
    "rgb(175,135,255)",
    "rgb(175,175,0)",
    "rgb(175,175,95)",
    "rgb(175,175,135)",
    "rgb(175,175,175)",
    "rgb(175,175,215)",
    "rgb(175,175,255)",
    "rgb(175,215,0)",
    "rgb(175,215,95)",
    "rgb(175,215,135)",
    "rgb(175,215,175)",
    "rgb(175,215,215)",
    "rgb(175,215,255)",
    "rgb(175,255,0)",
    "rgb(175,255,95)",
    "rgb(175,255,135)",
    "rgb(175,255,175)",
    "rgb(175,255,215)",
    "rgb(175,255,255)",
    "rgb(215,0,0)",
    "rgb(215,0,95)",
    "rgb(215,0,135)",
    "rgb(215,0,175)",
    "rgb(215,0,215)",
    "rgb(215,0,255)",
    "rgb(215,95,0)",
    "rgb(215,95,95)",
    "rgb(215,95,135)",
    "rgb(215,95,175)",
    "rgb(215,95,215)",
    "rgb(215,95,255)",
    "rgb(215,135,0)",
    "rgb(215,135,95)",
    "rgb(215,135,135)",
    "rgb(215,135,175)",
    "rgb(215,135,215)",
    "rgb(215,135,255)",
    "rgb(215,175,0)",
    "rgb(215,175,95)",
    "rgb(215,175,135)",
    "rgb(215,175,175)",
    "rgb(215,175,215)",
    "rgb(215,175,255)",
    "rgb(215,215,0)",
    "rgb(215,215,95)",
    "rgb(215,215,135)",
    "rgb(215,215,175)",
    "rgb(215,215,215)",
    "rgb(215,215,255)",
    "rgb(215,255,0)",
    "rgb(215,255,95)",
    "rgb(215,255,135)",
    "rgb(215,255,175)",
    "rgb(215,255,215)",
    "rgb(215,255,255)",
    "rgb(255,0,0)",
    "rgb(255,0,95)",
    "rgb(255,0,135)",
    "rgb(255,0,175)",
    "rgb(255,0,215)",
    "rgb(255,0,255)",
    "rgb(255,95,0)",
    "rgb(255,95,95)",
    "rgb(255,95,135)",
    "rgb(255,95,175)",
    "rgb(255,95,215)",
    "rgb(255,95,255)",
    "rgb(255,135,0)",
    "rgb(255,135,95)",
    "rgb(255,135,135)",
    "rgb(255,135,175)",
    "rgb(255,135,215)",
    "rgb(255,135,255)",
    "rgb(255,175,0)",
    "rgb(255,175,95)",
    "rgb(255,175,135)",
    "rgb(255,175,175)",
    "rgb(255,175,215)",
    "rgb(255,175,255)",
    "rgb(255,215,0)",
    "rgb(255,215,95)",
    "rgb(255,215,135)",
    "rgb(255,215,175)",
    "rgb(255,215,215)",
    "rgb(255,215,255)",
    "rgb(255,255,0)",
    "rgb(255,255,95)",
    "rgb(255,255,135)",
    "rgb(255,255,175)",
    "rgb(255,255,215)",
    "rgb(255,255,255)",
    "rgb(8,8,8)",
    "rgb(18,18,18)",
    "rgb(28,28,28)",
    "rgb(38,38,38)",
    "rgb(48,48,48)",
    "rgb(58,58,58)",
    "rgb(68,68,68)",
    "rgb(78,78,78)",
    "rgb(88,88,88)",
    "rgb(98,98,98)",
    "rgb(108,108,108)",
    "rgb(118,118,118)",
    "rgb(128,128,128)",
    "rgb(138,138,138)",
    "rgb(148,148,148)",
    "rgb(158,158,158)",
    "rgb(168,168,168)",
    "rgb(178,178,178)",
    "rgb(188,188,188)",
    "rgb(198,198,198)",
    "rgb(208,208,208)",
    "rgb(218,218,218)",
    "rgb(228,228,228)",
    "rgb(238,238,238)",
]


@rich.repr.auto
class ANSISegment(NamedTuple):
    delta_x: int | None = None
    delta_y: int | None = None
    absolute_x: int | None = None
    absolute_y: int | None = None
    content: Content | None = None
    replace: tuple[int | None, int | None] | None = None

    def __rich_repr__(self) -> rich.repr.Result:
        yield "delta_x", self.delta_x, None
        yield "delta_y", self.delta_y, None
        yield "absolute_x", self.absolute_x, None
        yield "absolute_y", self.absolute_y, None
        yield "content", self.content, None
        yield "replace", self.replace, None

    def get_replace_offsets(
        self, cursor_offset: int, line_length: int
    ) -> tuple[int, int]:
        assert self.replace is not None, (
            "Only call this if the replace attribute has a value"
        )
        replace_start, replace_end = self.replace
        if replace_start is None:
            replace_start = cursor_offset
        if replace_end is None:
            replace_end = cursor_offset
        if replace_start < 0:
            replace_start = line_length + replace_start
        if replace_end < 0:
            replace_end = line_length + replace_end
        return (replace_start, replace_end)


class ANSIStream:
    def __init__(self) -> None:
        self.parser = ANSIParser()
        self.style = Style()
        self.show_cursor = True
        self.current_directory = ""

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
                    style += Style(foreground=Color.parse(ANSI_COLORS[ansi_color]))
                case [48, 5, ansi_color, *codes]:
                    # Background ANSI
                    style += Style(background=Color.parse(ANSI_COLORS[ansi_color]))
                case [0, *codes]:
                    # reset
                    return None
                case [code, *codes]:
                    if sgr_style := SGR_STYLE_MAP.get(code):
                        style += sgr_style

        return style

    def feed(self, text: str) -> Iterable[ANSISegment]:
        for token in self.parser.feed(text):
            yield from self.on_token(token)

    ANSI_SEPARATORS = {
        "\n": ANSISegment(delta_y=+1, absolute_x=0),
        "\r": ANSISegment(absolute_x=0),
        "\x08": ANSISegment(delta_x=-1),
    }
    CLEAR_CURSOR_TO_END_OF_LINE = ANSISegment(replace=(None, -1), content=EMPTY_CONTENT)
    CLEAR_CURSOR_TO_BEGINNING_OF_LINE = ANSISegment(
        replace=(0, None), content=EMPTY_CONTENT
    )
    CLEAR_ENTIRE_LINE = ANSISegment(
        replace=(0, -1), content=EMPTY_CONTENT, absolute_x=0
    )

    @classmethod
    @lru_cache(maxsize=1024)
    def _parse_csi(cls, csi: str) -> ANSISegment | None:
        if match := re.match(r"\x1b\[(\d+)([ABCDGKH])", csi):
            match match.groups():
                case [param, "A"]:
                    cursor_move = int(param) if param else 1
                    return ANSISegment(delta_y=-cursor_move)
                case [param, "B"]:
                    cursor_move = int(param) if param else 1
                    return ANSISegment(delta_y=+cursor_move)
                case [param, "C"]:
                    cursor_move = int(param) if param else 1
                    return ANSISegment(delta_x=+cursor_move)
                case [param, "D"]:
                    cursor_move = int(param) if param else 1
                    return ANSISegment(delta_x=-cursor_move)
                case ["0" | "", "K"]:
                    return cls.CLEAR_CURSOR_TO_END_OF_LINE
                case ["1", "K"]:
                    return cls.CLEAR_CURSOR_TO_BEGINNING_OF_LINE
                case ["2", "K"]:
                    return cls.CLEAR_ENTIRE_LINE
        return None

    def on_token(self, token: ANSIToken) -> Iterable[ANSISegment]:
        match token:
            case Separator(separator):
                yield self.ANSI_SEPARATORS[separator]

            case OSC(osc):
                match osc.split(";"):
                    case ["8", *_, link]:
                        self.style += Style(link=link or None)
                    case ["2025", current_directory, *_]:
                        self.current_directory = current_directory

            case CSI(csi):
                if csi.endswith("m"):
                    if (sgr_style := self._parse_sgr(csi[2:-1])) is None:
                        self.style = NULL_STYLE
                    else:
                        self.style += sgr_style
                else:
                    if (ansi_segment := self._parse_csi(csi)) is not None:
                        yield ansi_segment

            case ANSIToken(text):
                if self.style:
                    content = Content.styled(text, self.style)
                else:
                    content = Content(text)
                yield ANSISegment(delta_x=len(content), content=content)


if __name__ == "__main__":
    from textual.content import Content

    from rich import print

    # content = Content.from_markup(
    #     "Hello\n[bold magenta]World[/]!\n[ansi_red]This is [i]red\nVisit [link='https://www.willmcgugan.com']My blog[/]."
    # )
    content = Content.from_markup(
        "[red]012345678901234567890123455678901234567789[/red] " * 2
    )
    # content = Content.from_markup("[link='https://www.willmcgugan.com']My blog[/].")
    ansi_text = "".join(
        segment.style.render(segment.text) if segment.style else segment.text
        for segment in content.render_segments()
    )
    # print(content)
    # print(repr(ansi_text))

    parser = ANSIStream()
    from itertools import batched

    for batch in batched(ansi_text, 1000):
        for ansi_segment in parser.feed("".join(batch)):
            print(repr(ansi_segment))

    # for line in parser.lines:
    #     print(line)
