from time import monotonic

from textual.widget import Widget

from textual.content import Content
from textual.reactive import reactive


class StrikeText(Widget):
    DEFAULT_CSS = """
    StrikeText {
        height: auto;
        &.-complete {
            text-style: strike;
            color: $text-primary;
        }
    }
    """

    strike_time: reactive[float | None] = reactive(None)

    def __init__(
        self,
        content: Content,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        self.content = content
        super().__init__(name=name, id=id, classes=classes)

    def strike(self) -> None:
        self.strike_time = monotonic()
        self.auto_refresh = 1 / 30

    def render(self) -> Content:
        content = self.content
        if self.strike_time is not None:
            position = int((monotonic() - self.strike_time) * 70)
            content = content.stylize("strike $text-primary", 0, position)
            if position > len(content):
                self.auto_refresh = None
        return content


if __name__ == "__main__":
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    class StrikeApp(App):
        CSS = """
        Screen {
            overflow: auto;
        }

        """
        BINDINGS = [("space", "strike", "Strike")]

        def compose(self) -> ComposeResult:
            for n in range(20):
                yield Static("HELLO")
            yield StrikeText(Content("Where there is a Will, there is a way"))
            for n in range(200):
                yield Static("World")

        def action_strike(self):
            self.query_one(StrikeText).strike()

    app = StrikeApp()
    app.run()
