from dataclasses import dataclass

from asyncio import Future
from textual.message import Message

import rich.repr

from toad.answer import Answer
from toad.acp import protocol
from toad.acp.encode_tool_call_id import encode_tool_call_id


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
