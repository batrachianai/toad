# mypy: disable-error-code="empty-body"
"""
ACP remote API
"""

from toad import jsonrpc
from toad.acp import protocol

API = jsonrpc.API()


@API.method()
def initialize(
    protocolVersion: int,
    clientCapabilities: protocol.ClientCapabilities,
    clientInfo: protocol.Implementation,
) -> protocol.InitializeResponse:
    """https://agentclientprotocol.com/protocol/initialization"""
    ...


@API.method(name="session/new")
def session_new(
    cwd: str, mcpServers: list[protocol.McpServer]
) -> protocol.NewSessionResponse:
    """https://agentclientprotocol.com/protocol/session-setup#session-id"""
    ...


@API.method(name="session/load")
def session_load(
    cmd: str, mcpServers: list[protocol.McpServer], sessionId: str
) -> protocol.LoadSessionResponse:
    """https://agentclientprotocol.com/protocol/session-setup#loading-a-session"""
    ...


@API.notification(name="session/cancel")
def session_cancel(sessionId: str, _meta: dict):
    """https://agentclientprotocol.com/protocol/prompt-turn#cancellation"""
    ...


@API.method(name="session/prompt")
def session_prompt(
    prompt: list[protocol.ContentBlock], sessionId: str
) -> protocol.SessionPromptResponse:
    """https://agentclientprotocol.com/protocol/prompt-turn#1-user-message"""
    ...


@API.method(name="session/set_mode")
def session_set_mode(sessionId: str, modeId: str) -> protocol.SetSessionModeResponse:
    """https://agentclientprotocol.com/protocol/session-modes#from-the-client"""
    ...
