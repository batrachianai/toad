from textual.app import ComposeResult
from textual import getters
from textual import containers
from textual.widget import Widget
from textual import widgets
from textual.reactive import var, reactive
from textual.timer import Timer


from toad.widgets.throbber import ThrobberVisual
from toad.session_tracker import SessionDetails


class SessionSummary(containers.HorizontalGroup):
    session_details: var[SessionDetails | None] = var(None, always_update=True)

    title = getters.query_one(".title", widgets.Label)
    subtitle = getters.query_one(".subtitle", widgets.Label)
    blink = reactive(False, toggle_class="-blink")

    def __init__(
        self,
        session_details: SessionDetails | None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.blink_timer: Timer | None = None
        self.set_reactive(SessionSummary.session_details, session_details)

    def watch_session_details(self, session_details: SessionDetails | None) -> None:
        self.remove_class(
            "-state-notready",
            "-state-busy",
            "-state-asking",
            "-state-idle",
            update=False,
        )
        if session_details is None:
            self.add_class("-state-notready")
            return
        self.title.update(session_details.title)
        self.subtitle.update(session_details.subtitle)
        self.add_class(f"-state-{session_details.state}")
        if self.blink_timer is not None:
            if session_details == "asking":
                self.blink_timer.resume()
            else:
                self.blink_timer.pause()
                self.blink_timer.reset()

    def on_mount(self) -> None:
        def do_blink() -> None:
            self.blink = not self.blink

        self.blink_timer = self.set_interval(0.5, do_blink, pause=False)

    def compose(self) -> ComposeResult:
        yield widgets.Label("❯", classes="icon")
        with containers.VerticalGroup():
            if (session_details := self.session_details) is not None:
                yield widgets.Label(
                    session_details.title,
                    classes="title",
                    markup=False,
                )
                yield widgets.Static(
                    ThrobberVisual(get_time=lambda: 0.0),
                    classes="busy-indicator",
                )
                yield widgets.Rule(line_style="heavy")
                yield widgets.Label(
                    session_details.subtitle,
                    classes="subtitle",
                    markup=False,
                )


if __name__ == "__main__":
    from textual.app import App

    session_details = SessionDetails(
        0,
        "mode",
        title="Building BMI calculator",
        subtitle="Claude Code",
    )

    class SessionApp(App):
        CSS_PATH = "../toad.tcss"
        CSS = """
        Screen {
            layout: horizontal;
        }
        """

        def compose(self) -> ComposeResult:
            yield SessionSummary(session_details, classes="-state-busy")
            yield SessionSummary(session_details, classes="-state-asking")
            yield SessionSummary(session_details, classes="-state-idle")

    SessionApp().run()
