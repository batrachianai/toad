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
    cwd: str, mcpServers: list[protocol.McpServer], sessionId: str
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


# ACP v2 (draft)
# https://agentclientprotocol.com/protocol/v2/migration


@API.method(name="initialize")
def initialize_v2(
    protocolVersion: int,
    capabilities: dict,
    info: protocol.Implementation,
) -> dict:
    """https://agentclientprotocol.com/protocol/v2/initialization"""
    ...


@API.method(name="session/resume")
def session_resume(
    sessionId: str,
    cwd: str,
    mcpServers: list[protocol.McpServer],
    replayFrom: dict | None,
) -> dict:
    """Resume (and optionally replay) an existing session (v2 replacement for session/load)."""
    ...


@API.method(name="session/prompt")
def session_prompt_v2(
    sessionId: str, prompt: list[protocol.ContentBlock], idempotencyKey: str
) -> dict:
    """v2 prompt. The response only acknowledges insertion; the turn ends with an idle `state_update`."""
    ...


@API.notification(name="session/cancel")
def session_cancel_v2(sessionId: str):
    """https://agentclientprotocol.com/protocol/v2/prompt-lifecycle"""
    ...


@API.method(name="session/set_config_option")
def session_set_config_option(
    sessionId: str, configId: str, type: str, value: str | bool
) -> dict:
    """v2 replacement for session/set_mode."""
    ...
