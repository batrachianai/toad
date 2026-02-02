from dataclasses import dataclass
from enum import auto, Enum


class SessionState(Enum):
    """Possible session state."""

    BUSY = auto()
    """Session is busy working."""
    ASKING = auto()
    """Session is asking user for permission."""
    IDLE = auto()
    """Session is idle, waiting for a prompt."""


@dataclass
class SessionMeta:
    """Tracks a concurrent session."""

    index: int
    """Index of session, used in sorting."""
    mode_name: str
    """The screen mode name."""
    title: str
    """The title of the conversation."""
    subtitle: str
    """The subtitle of the conversation."""
    state: SessionState
    """The current state of the session."""


class SessionTracker:
    """Tracks concurrent agent settings"""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionMeta] = {}
        self._session_index = 0

    def add_session(self, title: str, subtitle: str):
        self._session_index += 1
        mode_name = f"session-{self._session_index}"
        session_meta = SessionMeta(
            index=self._session_index,
            mode_name=mode_name,
            title=title,
            subtitle=subtitle,
            state=SessionState.IDLE,
        )
        self.sessions[mode_name] = session_meta
