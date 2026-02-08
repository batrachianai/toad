from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual import getters


from toad.app import ToadApp
from toad.widgets.session_grid_select import SessionGridSelect


class SessionScreen(ModalScreen):

    app: getters.app[ToadApp] = getters.app(ToadApp)

    def compose(self) -> ComposeResult:
        yield SessionGridSelect(self.app.session_tracker)
