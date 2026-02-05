from dataclasses import dataclass
from typing import Literal

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


class SessionTracker:
    """Tracks concurrent agent settings"""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionDetails] = {}
        self._session_index = 0

    def new_session(self) -> SessionDetails:
        self._session_index += 1
        mode_name = f"session-{self._session_index}"
        session_meta = SessionDetails(
            index=self._session_index,
            mode_name=mode_name,
        )
        return session_meta

    def update_session(
        self,
        mode_name: str,
        title: str | None,
        subtitle: str | None,
        state: SessionState | None,
    ) -> SessionDetails:
        session_meta = self.sessions[mode_name]
        if title is not None:
            session_meta.title = title
        if subtitle is not None:
            session_meta.subtitle = subtitle
        if state is not None:
            session_meta.state = state
        return session_meta
