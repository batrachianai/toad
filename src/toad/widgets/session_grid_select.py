from textual.app import ComposeResult
from textual import getters

from toad.app import ToadApp
from toad.widgets.grid_select import GridSelect
from toad.widgets.session_summary import SessionSummary
from toad.session_tracker import SessionTracker, SessionDetails


class SessionGridSelect(GridSelect):

    app: getters.app[ToadApp] = getters.app(ToadApp)

    def __init__(
        self,
        session_tracker: SessionTracker,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.session_tracker = session_tracker
        super().__init__(id=id, classes=classes)

    def on_mount(self) -> None:
        self.app.session_update_signal.subscribe(
            self, self.handle_session_update_signal
        )

    async def handle_session_update_signal(
        self, update: tuple[str, SessionDetails | None]
    ) -> None:
        self.notify(str(update))
        mode_name, details = update
        session_summary = self.query_one_optional(f"#{mode_name}", SessionSummary)
        if details is None:
            if session_summary is not None:
                await session_summary.remove()
            return

        if session_summary is None:
            await self.mount(SessionSummary(details, id=details.mode_name))
        else:
            session_summary.session_details = details

    def compose(self) -> ComposeResult:
        for session in self.session_tracker.ordered_sessions:
            yield SessionSummary(session, id=session.mode_name)
