"""
Protocol-specific handling of an ACP session.

An `Agent` owns the agent process and the JSON-RPC transport. Once the handshake has
negotiated a protocol version, the agent creates the matching `Session` subclass, which
implements the session methods (new, resume, prompt, ...) and exposes the client
methods the agent may call (session/update, session/request_permission, ...).
"""

import json
from abc import ABC, abstractmethod
from math import floor
from pathlib import Path
from typing import Any, ClassVar, NamedTuple, Protocol

from textual.content import Content
from textual.message import Message

from toad import jsonrpc
from toad.agent import AgentFail
from toad.agent_schema import Agent as AgentData
from toad.acp import messages
from toad.db import DB


class Mode(NamedTuple):
    """An agent mode."""

    id: str
    name: str
    description: str | None


class ContextUsage(NamedTuple):
    """Context window usage."""

    used: int
    size: int
    cost: Cost | None = None

    @property
    def percentage_used(self) -> float:
        try:
            return (self.used / self.size) * 100.0
        except ZeroDivisionError:
            # Sanity check. If size is 0, then 100% is always used?
            return 100.0

    @property
    def percentage_display(self) -> str:
        return f"{floor(self.percentage_used * 10) / 10:.1f}%"


class Cost(NamedTuple):
    """A cost with associated currency."""

    amount: float
    currency: str

    def __str__(self) -> str:
        return f"{self:}"

    def __format__(self, _specifier: str) -> str:
        from format_currency import format_currency

        amount, currency = self
        currency_text = format_currency(amount, currency_code=currency).replace(" ", "")
        return currency_text


class TokenUsage(NamedTuple):
    """Tokens used for a single prompt (per-turn)."""

    total_tokens: int
    input_tokens: int
    output_tokens: int
    thought_tokens: int | None
    cached_read_tokens: int | None
    cached_write_tokens: int | None


class Connection(Protocol):
    """What a session needs from the connection to the agent process."""

    def request(self) -> jsonrpc.Request:
        """Create a request to send to the agent."""
        ...

    def post_message(self, message: Message) -> bool:
        """Post a message to the UI."""
        ...

    def log(self, line: str) -> None:
        """Write to the agent log."""
        ...


class Session(ABC):
    """Base class for a session speaking a specific version of ACP."""

    PROTOCOL_VERSION: ClassVar[int]
    """The ACP version this class implements."""

    def __init__(
        self,
        connection: Connection,
        agent_data: AgentData,
        project_root: Path,
        initialize_response: dict[str, Any],
        session_id: str | None = None,
        session_pk: int | None = None,
    ) -> None:
        """
        Args:
            connection: Connection to the agent process.
            agent_data: Agent data.
            project_root: Project root path.
            initialize_response: The agent's response to `initialize`.
            session_id: Existing session id (to resume), or `None` for a new session.
            session_pk: Primary key of the session in the database, if resuming.
        """
        self.connection = connection
        self.agent_data = agent_data
        self.project_root_path = project_root
        self.session_id = session_id
        self.session_pk = session_pk
        self._context_usage: ContextUsage | None = None

    @property
    def agent_name(self) -> str:
        return self.agent_data["name"]

    @property
    @abstractmethod
    def supports_resume(self) -> bool:
        """Can this agent resume an existing session?"""

    @abstractmethod
    async def new_session(self) -> None:
        """Create a new session."""

    @abstractmethod
    async def resume_session(self) -> None:
        """Resume the existing session (`session_id`), replaying its history."""

    @abstractmethod
    async def prompt(self, prompt: list[Any]) -> str | None:
        """Send a prompt, and wait for the turn to end.

        Returns:
            The stop reason, or `None` if there was an error.
        """

    @abstractmethod
    async def set_mode(self, mode_id: str) -> str | None:
        """Set the agent's mode.

        Returns:
            An error message, or `None` on success.
        """

    @abstractmethod
    async def cancel(self) -> bool:
        """Cancel the current turn."""

    def connection_lost(self) -> None:
        """Called when the agent process exits."""

    def request(self) -> jsonrpc.Request:
        return self.connection.request()

    def post_message(self, message: Message) -> bool:
        return self.connection.post_message(message)

    def log(self, line: str) -> None:
        self.connection.log(line)

    async def record_session(self) -> None:
        """Save a new session in the database, if the agent can resume it later.

        The protocol version is recorded, so the session is resumed with the same one.
        """
        if not self.supports_resume:
            return
        assert self.session_id is not None
        db = DB()
        self.session_pk = await db.session_new(
            "New Session",
            self.agent_data["name"],
            self.agent_data["identity"],
            self.session_id,
            protocol="acp",
            meta={
                "cwd": str(self.project_root_path),
                "agent_data": {
                    **self.agent_data,
                    "acp_version": self.PROTOCOL_VERSION,
                },
            },
        )

    async def resume_cwd(self) -> str:
        """Get the working directory of the session being resumed.

        Also restores the agent data the session was created with.
        """
        cwd = str(self.project_root_path)
        if self.session_pk is not None:
            db = DB()
            if (session := await db.session_get(self.session_pk)) is not None:
                if session["meta_json"]:
                    meta = json.loads(session["meta_json"])
                    if session_cwd := meta.get("cwd", None):
                        cwd = session_cwd
                    if agent_data := meta.get("agent_data"):
                        self.agent_data = agent_data
        return cwd

    def set_context_usage(self, context_usage: ContextUsage) -> None:
        """Update context usage, and the status line."""
        self._context_usage = context_usage
        self.update_status_line()

    def update_status_line(self) -> None:
        """Update the current status line."""

        if (usage := self._context_usage) is not None:
            status: list[Content] = []
            status.append(
                Content.assemble(
                    f"{usage.used / 1000:.1f}K",
                    " (",
                    (f"{usage.percentage_display}", "bold"),
                    ")",
                )
            )
            if (cost := usage.cost) is not None:
                status.append(Content.assemble((f"{cost}", "bold")))

            status_line = Content(" • ").join(status)
            self.post_message(messages.UpdateStatusLine(status_line))

    async def wait_prompt_response(self, session_prompt: jsonrpc.MethodCall) -> Any:
        """Wait for the response to session/prompt, reporting errors to the UI.

        Returns:
            The result, or `None` if there was an error.
        """
        try:
            result = await session_prompt.wait()
        except jsonrpc.APIError as error:
            details = ""
            match error.data:
                case {"details": details}:
                    pass

            self.post_message(
                AgentFail(
                    "Failed to send prompt" or error.message,
                    (
                        str(details)
                        if details
                        else f"{self.agent_name} returned an error"
                    ),
                )
            )
            return None
        except jsonrpc.JSONRPCError as error:
            self.post_message(
                AgentFail(
                    "Failed to send prompt" or error.message,
                    (error.message or f"{self.agent_name} returned an error"),
                )
            )
            return None

        assert result is not None
        return result
