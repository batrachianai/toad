from functools import lru_cache
from time import monotonic

from rich.segment import Segment
from rich.style import Style as RichStyle

from textual.visual import Visual
from textual.color import Color, Gradient

from textual.style import Style
from textual.strip import Strip
from textual.visual import RenderOptions
from textual.widget import Widget
from textual.css.styles import RulesMap


COLORS = [
    "#881177",
    "#aa3355",
    "#cc6666",
    "#ee9944",
    "#eedd00",
    "#99dd55",
    "#44dd88",
    "#22ccbb",
    "#00bbcc",
    "#0099cc",
    "#3366bb",
    "#663399",
    "#881177",
]


class ThrobberVisual(Visual):
    """A Textual 'Visual' object.

    Analogous to a Rich renderable, but with support for transparency.

    """

    def __init__(
        self, character: str = "━", get_time: Callable[[], float] = monotonic
    ) -> None:
        self.character = character
        self.get_time = get_time

    gradient = Gradient.from_colors(*[Color.parse(color) for color in COLORS])

    @lru_cache(maxsize=8)
    def make_segments(self, style: Style, width: int) -> list[Segment]:
        gradient = self.gradient
        background = style.rich_style.bgcolor
        character = self.character
        segments = [
            Segment(
                character,
                RichStyle.from_color(
                    gradient.get_rich_color((offset / width) % 1),
                    background,
                ),
            )
            for offset in range(width * 2)
        ]

        return segments

    def render_strips(
        self, width: int, height: int | None, style: Style, options: RenderOptions
    ) -> list[Strip]:
        """Render the Visual into an iterable of strips.

        Args:
            width: Width of desired render.
            height: Height of desired render or `None` for any height.
            style: The base style to render on top of.
            options: Additional render options.

        Returns:
            An list of Strips.
        """

        time = self.get_time()
        segments = self.make_segments(style, width)
        offset = width - int((time % 1.0) * width)
        segments = segments[offset : offset + width]
        return [Strip(segments, cell_length=width)]

    def get_optimal_width(self, rules: RulesMap, container_width: int) -> int:
        return container_width

    def get_height(self, rules: RulesMap, width: int) -> int:
        return 1


class Throbber(Widget):
    def on_mount(self) -> None:
        self.auto_refresh = 1 / 15

    def render(self) -> ThrobberVisual:
        return ThrobberVisual()
