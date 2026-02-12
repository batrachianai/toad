from rich.console import RenderableType

from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import ScreenResume
from textual.screen import Screen, ModalScreen
from textual import getters
from textual.widget import Widget
from textual import widgets
from textual import containers
from textual.reactive import reactive
from textual.renderables.blank import Blank
from textual.renderables.background_screen import BackgroundScreen
from textual import on


from toad.app import ToadApp
from toad.widgets.grid_select import GridSelect
from toad.widgets.session_grid_select import SessionGridSelect
from toad.widgets.session_summary import SessionSummary


class SessionsScreen(ModalScreen[str]):
    CSS_PATH = "sessions.tcss"
    BINDINGS = [Binding("escape", "dismiss", "Dismiss")]

    app: getters.app[ToadApp] = getters.app(ToadApp)
    session_grid_select = getters.query_one(SessionGridSelect)
    background_mode = reactive("")

    def get_background_screen(self) -> Screen | None:
        background_mode = self.background_mode or self.app.current_mode
        screen_stack = self.app.get_screen_stack(background_mode)

        try:
            screen = (
                screen_stack[0]
                if (self.app.current_mode == background_mode)
                else screen_stack[-1]
            )
        except KeyError:
            return None
        if screen is self.screen:
            return None
        return screen

    def watch_background_mode(self):
        screen = self.get_background_screen()
        if screen is not None:
            screen.refresh()
        self.app.temporary_background_screen = screen

    def render(self) -> RenderableType:
        if (screen := self.get_background_screen()) is None:
            return Blank(self.background_colors[1])
        return BackgroundScreen(screen, self.styles.background)

    def compose(self) -> ComposeResult:
        with containers.Center(id="title-container"):
            yield widgets.Label("Sessions")
        yield SessionGridSelect(self.app.session_tracker)
        yield widgets.Footer()

    @property
    def focus_chain(self) -> list[Widget]:
        return [self.session_grid_select]

    async def _on_screen_resume(self, event: ScreenResume) -> None:
        current_mode = self.app.screen_stack[0].id
        if current_mode is not None:
            self.session_grid_select.update_current(current_mode)

    def _on_screen_suspend(self) -> None:
        current_mode = self.app.screen_stack[0].id
        if current_mode is not None:
            self.session_grid_select.update_current(current_mode)

    @on(GridSelect.Highlighted)
    def on_highlighted(self, event: GridSelect.Highlighted) -> None:
        if (
            isinstance(event.widget, SessionSummary)
            and event.widget.session_details is not None
        ):
            self.background_mode = event.widget.session_details.mode_name

    @on(GridSelect.Selected)
    def on_selected(self, event: GridSelect.Selected) -> None:
        if (
            isinstance(event.widget, SessionSummary)
            and event.widget.session_details is not None
        ):
            self.dismiss(event.widget.session_details.mode_name)
