from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import ScreenResume
from textual.screen import ModalScreen
from textual import getters
from textual import widgets
from textual import containers

from toad.app import ToadApp
from toad.widgets.session_grid_select import SessionGridSelect


class SessionsScreen(ModalScreen):
    CSS_PATH = "sessions.tcss"
    BINDINGS = [Binding("escape", "dismiss", "Dismiss")]

    app: getters.app[ToadApp] = getters.app(ToadApp)
    session_grid_select = getters.query_one(SessionGridSelect)

    def compose(self) -> ComposeResult:
        with containers.Center(id="title-container"):
            yield widgets.Label("Sessions")
        yield SessionGridSelect(self.app.session_tracker)
        yield widgets.Footer()

    def _on_screen_resume(self, event: ScreenResume) -> None:
        current_mode = self.app.screen_stack[0].id
        if current_mode is not None:
            self.session_grid_select.update_current(current_mode)
