from datetime import datetime, timezone
import json

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
                "⚠ Not all ACP agents currently support resume",
                classes="warning",
            )
            with containers.Center(id="table-container"):
                yield widgets.DataTable(id="sessions", cursor_type="row")
            with containers.HorizontalGroup(id="buttons"):
                yield widgets.Button(
                    "Resume", id="resume", variant="primary", disabled=True
                )
                yield widgets.Button("Cancel", id="cancel")

    @classmethod
    def friendly_time_ago(cls, iso_timestamp: str) -> str:
        """
        Convert ISO timestamp to friendly time description.

        Args:
            iso_timestamp: ISO format timestamp string (e.g., '2024-01-30T15:30:00+00:00')

        Returns:
            - "just now" if < 1 minute ago
            - "X minute(s) ago" if < 1 hour ago
            - "X hour(s) ago" if < 24 hours ago
            - Local datetime string if >= 24 hours ago (format: 'YYYY-MM-DD HH:MM AM/PM')

        Examples:
            >>> friendly_time_ago('2024-01-30T15:30:00+00:00')  # 30 seconds ago
            'just now'
            >>> friendly_time_ago('2024-01-30T15:00:00+00:00')  # 5 minutes ago
            '5 minutes ago'
            >>> friendly_time_ago('2024-01-30T13:00:00+00:00')  # 3 hours ago
            '3 hours ago'
            >>> friendly_time_ago('2024-01-28T15:30:00+00:00')  # 2 days ago
            '2024-01-28 10:30 AM'  # (in local time)
        """
        # Parse the timestamp
        past_dt = datetime.fromisoformat(iso_timestamp)

        # Get current time in appropriate timezone
        if past_dt.tzinfo is not None:
            # Timezone-aware: use UTC for comparison
            now = datetime.now(timezone.utc)
        else:
            # Naive datetime: use naive now
            now = datetime.now()

        # Calculate time difference
        diff = now - past_dt
        total_seconds = diff.total_seconds()

        # Less than 1 minute
        if total_seconds < 60:
            return "just now"

        # Less than 1 hour (3600 seconds)
        if total_seconds < 3600:
            minutes = int(total_seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

        # Less than 24 hours (86400 seconds)
        if total_seconds < 86400:
            hours = int(total_seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"

        # 24 hours or more - return as local time
        if past_dt.tzinfo is not None:
            local_dt = past_dt.astimezone()  # Convert to local timezone
        else:
            local_dt = past_dt  # Already naive, assume local

        return local_dt.strftime("%c")

    async def on_mount(self) -> None:
        table = self.session_table
        table.add_columns("Agent", "Session", "Created", "Last Used", "Path")
        db = DB()
        sessions = await db.session_get_recent()
        if sessions is None:
            return

        for session in sessions:
            cwd = ""
            if meta_json := session["meta_json"]:
                try:
                    cwd = json.loads(meta_json).get("cwd", None)
                except Exception:
                    pass

            table.add_row(
                session["agent"],
                session["title"],
                self.friendly_time_ago(session["created_at"]),
                self.friendly_time_ago(session["last_used"]),
                cwd,
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
