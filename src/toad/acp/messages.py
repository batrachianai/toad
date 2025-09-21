from dataclasses import dataclass

from asyncio import Future
from textual.message import Message

from toad.answer import Answer
from toad.acp import protocol


class ACPAgentMessage(Message):
    pass


@dataclass
class ACPThinking(ACPAgentMessage):
    type: str
    text: str


@dataclass
class ACPUpdate(ACPAgentMessage):
    type: str
    text: str


@dataclass
class ACPRequestPermission(ACPAgentMessage):
    options: list[protocol.PermissionOption]
    tool_call: protocol.ToolCallUpdate
    result_future: Future[Answer]
