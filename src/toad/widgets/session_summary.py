from textual.app import ComposeResult
from textual import getters
from textual import containers
from textual import widgets
from textual.reactive import reactive
from textual.timer import Timer


from toad.widgets.condensed_path import CondensedPath
from toad.widgets.throbber import ThrobberVisual
from toad.session_tracker import SessionDetails


class BusyIndicator(widgets.Static):
    def render(self) -> ThrobberVisual:
        return ThrobberVisual("▔")

    def on_mount(self) -> None:
        self.auto_refresh = 1 / 4


class SessionSummary(containers.VerticalGroup):
    session_details: reactive[SessionDetails | None] = reactive(
        None, always_update=True, recompose=True
    )

    title = getters.query_one(".title", widgets.Label)
    subtitle = getters.query_one(".subtitle", widgets.Label)
    current = reactive(True, toggle_class="-current", init=False, recompose=True)
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

    def on_mount(self) -> None:

        def do_blink() -> None:
            self.blink = not self.blink

        self.blink_timer = self.set_interval(0.5, do_blink, pause=False)

    def watch_current(self, current: bool) -> None:
        if (session_details := self.session_details) is not None:
            if current:
                self.title.update(f"✱{session_details.title}")
            else:
                self.title.update(session_details.title)

    def compose(self) -> ComposeResult:
        if (session_details := self.session_details) is not None:
            self.remove_class(
                "-state-notready",
                "-state-busy",
                "-state-asking",
                "-state-idle",
                update=False,
            )
            self.add_class(f"-state-{session_details.state}")

        yield BusyIndicator()
        # yield widgets.Rule(line_style="heavy")
        with containers.HorizontalGroup():
            yield widgets.Label("❯", classes="icon")
            with containers.VerticalGroup():
                if session_details is not None:
                    yield widgets.Label(
                        (
                            f"✱{session_details.title}"
                            if self.current
                            else session_details.title
                        ),
                        classes="title",
                        markup=False,
                    )
                    yield widgets.Label(
                        session_details.subtitle,
                        classes="subtitle",
                        markup=False,
                    )
                    with containers.HorizontalGroup():
                        yield widgets.Label("📁 ")
                        yield CondensedPath(session_details.path)


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
