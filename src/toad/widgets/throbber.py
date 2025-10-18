from time import monotonic
from typing import Callable

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
]


class ThrobberVisual(Visual):
    """A Textual 'Visual' object.

    Analogous to a Rich renderable, but with support for transparency.

    """

    gradient = Gradient.from_colors(*[Color.parse(color) for color in COLORS])

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

        time = monotonic()
        gradient = self.gradient
        background = style.rich_style.bgcolor

        strips = [
            Strip(
                [
                    Segment(
                        "━",
                        RichStyle.from_color(
                            gradient.get_rich_color((offset / width - time) % 1.0),
                            background,
                        ),
                    )
                    for offset in range(width)
                ],
                width,
            )
        ]
        return strips

    def get_optimal_width(self, rules: RulesMap, container_width: int) -> int:
        return container_width

    def get_height(self, rules: RulesMap, width: int) -> int:
        return 1


class Throbber(Widget):
    def on_mount(self) -> None:
        self.auto_refresh = 1 / 15

    def render(self) -> ThrobberVisual:
        return ThrobberVisual()
