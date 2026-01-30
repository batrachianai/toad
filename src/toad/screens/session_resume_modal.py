from textual import on
from textual.app import ComposeResult
from textual import getters
from textual import widgets
from textual import containers
from textual.screen import ModalScreen

from toad.db import DB, Session

HELP = """\
# Session Resume

Pick a session to resume.
"""


class SessionResumeModal(ModalScreen[Session]):
    """Dialog to select a session to resume."""

    CSS_PATH = "session_resume_modal.tcss"

    BINDINGS = [("escape", "dismiss", "Dismiss")]

    session_table = getters.query_one("#sessions", widgets.DataTable)

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="container"):
            yield widgets.Markdown(HELP)
            yield widgets.Static(
                "⚠ Most ACP agents currently do not support session resume — this feature is untested",
                classes="warning",
            )
            with containers.Center(id="table-container"):
                yield widgets.DataTable(id="sessions", cursor_type="row")
            with containers.HorizontalGroup(id="buttons"):
                yield widgets.Button(
                    "Resume", id="resume", variant="primary", disabled=True
                )
                yield widgets.Button("Cancel", id="cancel")

    async def on_mount(self) -> None:
        table = self.session_table
        table.add_columns("Agent", "Session", "Last Used")
        db = DB()
        sessions = await db.session_get_recent()
        if sessions is None:
            return
        for session in sessions:
            table.add_row(
                session["agent"],
                session["title"],
                session["created_at"],
                key=str(session["id"]),
            )

    @on(widgets.Button.Pressed, "#resume")
    async def on_resume_button(self) -> None:
        table = self.session_table
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key is None:
            return
        try:
            session_id = int(row_key.value)
        except ValueError:
            return
        db = DB()
        session = await db.session_get(session_id)
        self.dismiss(session)

    @on(widgets.Button.Pressed, "#cancel")
    def on_cancel_button(self) -> None:
        self.dismiss()

    @on(widgets.DataTable.RowHighlighted)
    def on_data_table_row_highlighted(self) -> None:
        self.query_one("#resume").disabled = False

    @on(widgets.DataTable.RowSelected)
    async def on_data_table_row_selected(
        self, event: widgets.DataTable.RowSelected
    ) -> None:
        if event.row_key is None:
            return
        self.log(event.row_key)
        try:
            session_id = int(event.row_key.value)
        except ValueError:
            return
        db = DB()
        session = await db.session_get(session_id)
        self.dismiss(session)


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    class TApp(App):
        def on_mount(self):
            self.push_screen(SessionResumeModal())

    app = TApp()
    app.run()
