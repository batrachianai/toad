"""
ACP initialization and protocol version negotiation.

https://agentclientprotocol.com/protocol/v2/initialization
"""

from typing import Any, NamedTuple

import toad
from toad import jsonrpc
from toad.acp import api
from toad.acp import protocol
from toad.acp.session import Connection

DEFAULT_VERSION = 1
"""The version requested when an agent doesn't set `acp_version`."""


class Handshake(NamedTuple):
    """The result of initializing an agent."""

    requested: int
    """The protocol version requested."""
    version: int
    """The negotiated protocol version."""
    response: dict[str, Any]
    """The agent's response to `initialize`."""

    @property
    def fell_back(self) -> bool:
        return self.version != self.requested


def _client_info() -> protocol.Implementation:
    return {"name": toad.NAME, "title": toad.TITLE, "version": toad.get_version()}


async def _initialize_v1(connection: Connection) -> dict[str, Any]:
    """https://agentclientprotocol.com/protocol/initialization"""
    with connection.request():
        initialize_response = api.initialize(
            1,
            {"fs": {"readTextFile": True, "writeTextFile": True}, "terminal": True},
            _client_info(),
        )
    return dict(await initialize_response.wait() or {})


async def _initialize_v2(connection: Connection) -> dict[str, Any]:
    """https://agentclientprotocol.com/protocol/v2/initialization"""
    with connection.request():
        initialize_response = api.initialize_v2(2, {}, _client_info())
    return await initialize_response.wait() or {}


_INITIALIZE = {1: _initialize_v1, 2: _initialize_v2}

SUPPORTED_VERSIONS = tuple(_INITIALIZE)
"""The ACP versions Toad can speak (2 is the draft pinned in `toad.acp.session_v2`)."""


async def negotiate(connection: Connection, requested: int) -> Handshake:
    """Initialize the agent, falling back to v1 if it doesn't support the requested version.

    Re-sending `initialize` is allowed before any other request.
    """
    if requested not in SUPPORTED_VERSIONS:
        raise ValueError(f"ACP v{requested} is not supported")
    if requested != 1:
        try:
            response = await _INITIALIZE[requested](connection)
            if response.get("protocolVersion") == requested:
                return Handshake(requested, requested, response)
        except jsonrpc.APIError as error:
            # -32022 means unsupported version; a strict v1 agent may return another error
            connection.log(f"[client] ACP v{requested} initialize failed: {error}")
    return Handshake(requested, 1, await _initialize_v1(connection))
