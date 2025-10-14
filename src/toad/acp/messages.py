from dataclasses import dataclass

from asyncio import Future
from typing import Mapping, TYPE_CHECKING
from textual.message import Message

import rich.repr

from toad.answer import Answer
from toad.acp import protocol
from toad.acp.encode_tool_call_id import encode_tool_call_id

if TYPE_CHECKING:
    from toad.widgets.terminal import TerminalState


class AgentMessage(Message):
    pass


@dataclass
class Thinking(AgentMessage):
    type: str
    text: str


@dataclass
class Update(AgentMessage):
    type: str
    text: str


@dataclass
@rich.repr.auto
class RequestPermission(AgentMessage):
    options: list[protocol.PermissionOption]
    tool_call: protocol.ToolCallUpdatePermissionRequest
    result_future: Future[Answer]


@dataclass
class Plan(AgentMessage):
    entries: list[protocol.PlanEntry]


@dataclass
class ToolCall(AgentMessage):
    tool_call: protocol.ToolCall

    @property
    def tool_id(self) -> str:
        """An id suitable for use as a TCSS ID."""
        return encode_tool_call_id(self.tool_call["toolCallId"])


@dataclass
class ToolCallUpdate(AgentMessage):
    tool_call: protocol.ToolCall
    update: protocol.ToolCallUpdate

    @property
    def tool_id(self) -> str:
        """An id suitable for use as a TCSS ID."""
        return encode_tool_call_id(self.tool_call["toolCallId"])


@dataclass
class AvailableCommandsUpdate(AgentMessage):
    """The agent is reporting its slash commands."""

    commands: list[protocol.AvailableCommand]


@dataclass
class CreateTerminal(AgentMessage):
    """Request a terminal in the conversation."""

    terminal_id: str
    command: str
    args: list[str] | None = None
    cwd: str | None = None
    env: Mapping[str, str] | None = None
    output_byte_limit: int | None = None


@dataclass
class KillTerminal(AgentMessage):
    """Kill a terminal process."""

    terminal_id: str


@dataclass
class GetTerminalState(AgentMessage):
    """Get the state of the terminal."""

    terminal_id: str
    result_future: Future[TerminalState]


@dataclass
class ReleaseTerminal(AgentMessage):
    """Release the terminal."""

    terminal_id: str


@dataclass
class WaitForTerminalExit(AgentMessage):
    """Wait for the terminal to exit."""

    terminal_id: str
    result_future: Future[tuple[int, str | None]]
