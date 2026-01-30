from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from textual.content import Content
from textual.message import Message


class AgentReady(Message):
    """Agent is ready."""


@dataclass
class AgentFail(Message):
    """Agent failed to start."""

    message: str
    details: str = ""
    help: str = "fail"


class AgentBase(ABC):
    """Base class for an 'agent'."""

    def __init__(self, project_root: Path) -> None:
        self.project_root_path = project_root
        super().__init__()

    @abstractmethod
    async def send_prompt(self, prompt: str) -> str | None:
        """Send a prompt to the agent.

        Args:
            prompt: Prompt text.

        Returns:
            str: The stop reason.
        """

    async def set_mode(self, mode_id: str) -> str | None:
        """Put the agent in a new mode.

        Args:
            mode_id: Mode id.

        Returns:
            str: The stop reason.
        """

    async def cancel(self) -> bool:
        """Cancel prompt.

        Returns:
            bool: `True` if success, `False` if the turn wasn't cancelled.

        """
        return False

    async def set_session_name(self, name: str) -> None:
        """Set the session name.

        Args:
            name: New name for the session.
        """

    def get_info(self) -> Content:
        return Content("")

    async def stop(self) -> None:
        """Stop the agent (gracefully exit the process)"""
