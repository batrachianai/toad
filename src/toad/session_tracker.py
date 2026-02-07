from dataclasses import dataclass
from operator import attrgetter
from typing import Iterable, Literal, Sequence

from textual.signal import Signal

type SessionState = Literal["notready", "busy", "asking", "idle"]


@dataclass
class SessionDetails:
    """Tracks a concurrent session."""

    index: int
    """Index of session, used in sorting."""
    mode_name: str
    """The screen mode name."""
    title: str = ""
    """The title of the conversation."""
    subtitle: str = ""
    """The subtitle of the conversation."""
    state: SessionState = "notready"
    """The current state of the session."""
    summary: str = ""
    """Suplimentary information about the session."""

    updates: int = 0
    """Track updates to the session details."""


class SessionTracker:
    """Tracks concurrent agent settings"""

    def __init__(self, signal: Signal[tuple[str, SessionDetails | None]]) -> None:
        self.sessions: dict[str, SessionDetails] = {}
        self._session_index = 0
        self.signal = signal

    def new_session(self) -> SessionDetails:
        self._session_index += 1
        mode_name = f"session-{self._session_index}"
        session_meta = SessionDetails(
            index=self._session_index,
            mode_name=mode_name,
        )
        self.sessions[mode_name] = session_meta
        return session_meta

    def get_session(self, mode_name: str) -> SessionDetails | None:
        return self.sessions.get(mode_name, None)

    def update_session(
        self,
        mode_name: str,
        title: str | None = None,
        subtitle: str | None = None,
        state: SessionState | None = None,
    ) -> SessionDetails:
        session_meta = self.sessions[mode_name]
        if title is not None:
            session_meta.title = title
        if subtitle is not None:
            session_meta.subtitle = subtitle
        if state is not None:
            session_meta.state = state
        self.signal.publish((mode_name, session_meta))
        return session_meta

    @property
    def ordered_sessions(self) -> Sequence[SessionDetails]:
        return sorted(self.sessions.values(), key=attrgetter("index"))

    def __iter__(self) -> Iterable[SessionDetails]:
        return iter(self.ordered_sessions)

    def session_cursor_move(
        self, mode_name: str, direction: Literal[-1, +1]
    ) -> str | None:
        mode_names = [session.mode_name for session in self.ordered_sessions]
        try:
            mode_index = mode_names.index(mode_name)
        except ValueError:
            return None
        mode_index = (mode_index + direction) % len(mode_names)
        new_mode_name = mode_names[mode_index]
        return new_mode_name
