"""
An ACP v2 (draft) session.

v2 reports session state as upserts, patches, and chunks keyed by stable ids. The
helpers in `toad.acp.v2` translate that state into the v1-shaped messages the UI renders.

Spec baseline
-------------

ACP v2 is still a draft, so this implementation is pinned to one release of it:

- Repository: https://github.com/agentclientprotocol/agent-client-protocol
- Release:    `schema-v2.0.0-beta.3` (published 2026-11-21; `toad.acp.v2.SCHEMA_RELEASE`)
- Schema:     `schema/v2/schema.json`, sha256 48b0a929...dd42c0b (unchanged since
              commit 26b362c). The stable v2 schema only, not `schema.unstable.json`.
- Docs:       https://agentclientprotocol.com/protocol/v2/migration

To move to a newer draft, diff the schema between the two releases, then apply each
change here (wire handling) or in `toad.acp.v2` (translation for the UI), and update
`SCHEMA_RELEASE` and the details above:

    git diff schema-v2.0.0-beta.3 <new-release> -- schema/v2/schema.json

Not implemented (deliberately) at this baseline, so look for changes to these in a
newer draft only if adding support:

- Agent methods: `session/list`, `session/close`, `session/delete`, `auth/login`,
  `auth/logout`, `tool_call/cancel`, `terminal/cancel`.
- Client methods: `elicitation/create`, `elicitation/complete` (no `elicitation`
  capability is advertised, so agents must not call them).
- Session updates that are logged and ignored: `notice`, `compaction_update`,
  `compaction_summary_chunk`, `subagent_update`, `session_message`,
  `session_message_chunk`, `session_info_update`, `replay_complete`.
- Session options: `additionalDirectories`, `systemPrompt`, and MCP servers (an
  empty `mcpServers` list is sent).
- Background work reported in `state_update.background`.
"""

import asyncio
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
import uuid
from typing import Any, cast

from toad import jsonrpc
from toad.agent import AgentFail
from toad.agent_schema import Agent as AgentData
from toad.acp import api
from toad.acp import messages
from toad.acp import protocol
from toad.acp import v2
from toad.acp.session import Connection, ContextUsage, Cost, Mode, Session
from toad.answer import Answer


class _Turn:
    """Tracks a prompt turn, which ends with an idle `state_update`."""

    def __init__(self) -> None:
        self.future: asyncio.Future[tuple[str | None, dict | None]] = (
            asyncio.get_running_loop().create_future()
        )
        self.started = False
        """Agent reported foreground work since the prompt was sent."""
        self.inserted = False
        """Agent acknowledged the prompt."""

    def finish(self, stop_reason: str | None, error: dict | None = None) -> None:
        if not self.future.done():
            self.future.set_result((stop_reason, error))


class SessionV2(Session):
    """A session speaking ACP v2 (draft)."""

    PROTOCOL_VERSION = v2.PROTOCOL_VERSION

    def __init__(
        self,
        connection: Connection,
        agent_data: AgentData,
        project_root: Path,
        initialize_response: dict[str, Any],
        session_id: str | None = None,
        session_pk: int | None = None,
    ) -> None:
        super().__init__(
            connection,
            agent_data,
            project_root,
            initialize_response,
            session_id,
            session_pk,
        )
        capabilities = initialize_response.get("capabilities")
        self.capabilities: dict[str, Any] = (
            capabilities if isinstance(capabilities, dict) else {}
        )
        self.auth_methods: list[dict[str, Any]] = (
            initialize_response.get("authMethods") or []
        )

        self._tool_calls: dict[str, dict[str, Any]] = {}
        self._terminals: dict[str, v2.Terminal] = {}
        self._dirty_terminals: set[str] = set()
        self._terminal_refresh: asyncio.TimerHandle | None = None
        self._message_text = v2.MessageText()
        self._own_message_ids: set[str] = set()
        self._prompt_in_flight = False
        self._turn: _Turn | None = None
        self._mode_config_id: str | None = None
        self._cost: Cost | None = None
        self._plan_ids: list[str] = []
        self._pending_permissions: dict[int | str, asyncio.Future[Answer]] = {}

    @property
    def supports_resume(self) -> bool:
        # session/resume is part of the baseline `session` capability in v2
        return self.capabilities.get("session") is not None

    def connection_lost(self) -> None:
        if (turn := self._turn) is not None:
            turn.finish(None)

    @jsonrpc.expose("session/update")
    def rpc_session_update(
        self,
        sessionId: str,
        update: dict[str, Any],
        _meta: dict[str, Any] | None = None,
    ) -> None:
        """Handle a `session/update`.

        https://agentclientprotocol.com/protocol/v2/prompt-lifecycle
        """
        match update.get("sessionUpdate"):
            case "agent_message_chunk" | "agent_thought_chunk" | "user_message_chunk":
                content = update.get("content")
                if isinstance(content, dict):
                    message_id = str(update.get("messageId", ""))
                    text = self._message_text.chunk(
                        update["sessionUpdate"], message_id, content
                    )
                    self._post_message_text(update["sessionUpdate"], message_id, text)

            case "agent_message" | "agent_thought" | "user_message":
                if "content" not in update:
                    return
                message_id = str(update.get("messageId", ""))
                delta = self._message_text.upsert(
                    update["sessionUpdate"], message_id, update["content"]
                )
                if delta is None:
                    self.log(
                        f"[client] message {message_id!r} was rewritten; not shown"
                    )
                else:
                    self._post_message_text(update["sessionUpdate"], message_id, delta)

            case "tool_call_update":
                tool_call_id = update.get("toolCallId")
                if isinstance(tool_call_id, str):
                    self._tool_calls[tool_call_id] = v2.patch_tool_call(
                        self._tool_calls.get(tool_call_id), update
                    )
                    self._post_tool_call(tool_call_id)

            case "tool_call_content_chunk":
                tool_call_id = update.get("toolCallId")
                content = update.get("content")
                if isinstance(tool_call_id, str) and isinstance(content, dict):
                    self._tool_calls[tool_call_id] = v2.append_tool_call_content(
                        self._tool_calls.get(tool_call_id), tool_call_id, content
                    )
                    self._post_tool_call(tool_call_id)

            case "terminal_update":
                if isinstance(terminal_id := update.get("terminalId"), str):
                    terminal = self._terminals.setdefault(
                        terminal_id, v2.Terminal(terminal_id)
                    )
                    terminal.apply_update(update)
                    self._refresh_terminal(terminal_id)

            case "terminal_output_chunk":
                if isinstance(terminal_id := update.get("terminalId"), str):
                    terminal = self._terminals.setdefault(
                        terminal_id, v2.Terminal(terminal_id)
                    )
                    terminal.append(str(update.get("data", "")))
                    self._refresh_terminal(terminal_id)

            case "plan_update":
                plan = update.get("plan") or {}
                if (plan_id := plan.get("planId")) is not None:
                    with suppress(ValueError):
                        self._plan_ids.remove(plan_id)
                    self._plan_ids.append(plan_id)
                self.post_message(
                    messages.Plan(cast(list[protocol.PlanEntry], v2.plan_entries(plan)))
                )

            case "plan_removed":
                plan_id = update.get("planId")
                if plan_id in self._plan_ids:
                    was_shown = self._plan_ids[-1] == plan_id
                    self._plan_ids.remove(plan_id)
                    if was_shown:
                        self.post_message(messages.Plan([]))

            case "available_commands_update":
                self._post_available_commands(update.get("availableCommands"))

            case "config_option_update":
                self._apply_config_options(update.get("configOptions"))

            case "usage_update":
                if "cost" in update:
                    match update["cost"]:
                        case {"amount": amount, "currency": currency}:
                            self._cost = Cost(amount, currency)
                        case _:
                            self._cost = None
                self.set_context_usage(
                    ContextUsage(
                        update.get("used", 0), update.get("size", 0), self._cost
                    )
                )

            case "state_update":
                if (turn := self._turn) is not None:
                    if update.get("state") == "idle":
                        if turn.started or turn.inserted:
                            error = update.get("error")
                            turn.finish(
                                update.get("stopReason"),
                                error if isinstance(error, dict) else None,
                            )
                    else:
                        # running, requires_action, or unknown (not idle)
                        turn.started = True

            case other:
                self.log(f"[client] ignoring session update {other!r}")

    def _post_message_text(self, kind: str, message_id: str, text: str) -> None:
        """Post message text to the UI."""
        if not text:
            return
        if kind.startswith("agent_message"):
            self.post_message(messages.Update("text", text))
        elif kind.startswith("agent_thought"):
            self.post_message(messages.Thinking("text", text))
        elif kind.startswith("user_message"):
            # The UI already shows prompts sent from Toad; only show other user
            # messages (such as those replayed on resume).
            if self._prompt_in_flight or message_id in self._own_message_ids:
                self._own_message_ids.add(message_id)
            else:
                self.post_message(messages.UserMessage("text", text))

    def _post_tool_call(self, tool_call_id: str) -> None:
        """Send the current state of a tool call to the UI."""
        tool_call = cast(
            protocol.ToolCall,
            v2.to_v1_tool_call(self._tool_calls[tool_call_id], self._terminals),
        )
        self.post_message(
            messages.ToolCallUpdate(
                deepcopy(tool_call), cast(protocol.ToolCallUpdate, tool_call)
            )
        )

    def _refresh_terminal(self, terminal_id: str) -> None:
        """Schedule a refresh of tool calls showing a terminal (batches rapid output)."""
        self._dirty_terminals.add(terminal_id)
        if self._terminal_refresh is None:
            self._terminal_refresh = asyncio.get_running_loop().call_later(
                0.1, self._flush_terminals
            )

    def _flush_terminals(self) -> None:
        self._terminal_refresh = None
        dirty_terminals = self._dirty_terminals
        self._dirty_terminals = set()
        for tool_call_id, tool_call in self._tool_calls.items():
            if v2.tool_call_terminals(tool_call) & dirty_terminals:
                self._post_tool_call(tool_call_id)

    def _post_available_commands(self, commands: list | None) -> None:
        self.post_message(
            messages.AvailableCommandsUpdate(
                cast(list[protocol.AvailableCommand], v2.available_commands(commands))
            )
        )

    def _apply_config_options(self, config_options: list | None) -> None:
        """Expose a 'mode' config option as Toad modes."""
        if (mode_option := v2.find_mode_option(config_options)) is None:
            return
        self._mode_config_id = mode_option.config_id
        modes = {
            mode_id: Mode(mode_id, name, description)
            for mode_id, name, description in mode_option.modes
        }
        if mode_option.current in modes:
            self.post_message(messages.SetModes(mode_option.current, modes))

    def _apply_session_setup(self, response: dict[str, Any]) -> None:
        """Apply the config options and commands from session/new or session/resume."""
        if "availableCommands" in response:
            self._post_available_commands(response["availableCommands"])
        self._apply_config_options(response.get("configOptions"))

    @jsonrpc.expose("session/request_permission")
    async def rpc_request_permission(
        self,
        sessionId: str,
        title: str,
        options: list[dict[str, Any]],
        description: str | None = None,
        subject: dict[str, Any] | None = None,
        _meta: dict | None = None,
    ) -> protocol.RequestPermissionResponse:
        """Agent requests permission.

        https://agentclientprotocol.com/rfds/v2/permission-requests

        Args:
            sessionId: The session ID.
            title: What permission is being requested.
            options: A list of permission options (potential replies).
            description: Optional details.
            subject: What the permission is for (a tool call or a command).
            _meta: Optional meta information.

        Returns:
            The response to the permission request.
        """
        request_id = jsonrpc.current_request_id.get()
        tool_call: dict[str, Any]
        match subject or {}:
            case {
                "type": "tool_call",
                "toolCall": {"toolCallId": str(tool_call_id)} as tool_call_update,
            }:
                # Applied like a tool_call_update before being shown
                self._tool_calls[tool_call_id] = v2.patch_tool_call(
                    self._tool_calls.get(tool_call_id), tool_call_update
                )
                self._post_tool_call(tool_call_id)
                tool_call = v2.to_v1_tool_call(
                    self._tool_calls[tool_call_id], self._terminals
                )
            case {"type": "command", "command": str(command)} as command_subject:
                tool_call = {
                    "toolCallId": command_subject.get("toolCallId")
                    or f"permission-{request_id}",
                    "kind": "execute",
                    "status": "pending",
                    "rawInput": {"command": command, "cwd": command_subject.get("cwd")},
                    "content": [
                        {
                            "type": "content",
                            "content": {"type": "text", "text": f"$ {command}"},
                        }
                    ],
                }
            case _:
                tool_call = {
                    "toolCallId": f"permission-{request_id}",
                    "kind": "other",
                    "status": "pending",
                    "content": [],
                }
        tool_call["title"] = title
        if description:
            tool_call["content"] = [
                {"type": "content", "content": {"type": "text", "text": description}},
                *(tool_call.get("content") or []),
            ]

        result_future: asyncio.Future[Answer] = asyncio.Future()
        if request_id is not None:
            self._pending_permissions[request_id] = result_future

        self.post_message(
            messages.RequestPermission(
                cast(list[protocol.PermissionOption], options),
                cast(protocol.ToolCallUpdatePermissionRequest, tool_call),
                result_future,
            )
        )
        try:
            # The future is cancelled if the agent sends $/cancel_request
            await asyncio.wait({result_future})
        finally:
            if request_id is not None:
                self._pending_permissions.pop(request_id, None)

        if result_future.done() and not result_future.cancelled():
            return {
                "outcome": {
                    "outcome": "selected",
                    "optionId": result_future.result().id,
                }
            }
        return {"outcome": cast(protocol.OutcomeSelected, {"outcome": "cancelled"})}

    @jsonrpc.expose("$/cancel_request")
    def rpc_cancel_request(
        self, requestId: int | str, _meta: dict | None = None
    ) -> None:
        """Agent no longer needs a response to a request it made."""
        if (result_future := self._pending_permissions.get(requestId)) is not None:
            result_future.cancel()

    async def new_session(self) -> None:
        with self.request():
            session_new_response = api.session_new(str(self.project_root_path), [])
        response = cast(dict[str, Any], await session_new_response.wait())
        assert response is not None
        self.session_id = response["sessionId"]
        await self.record_session()
        self._apply_session_setup(response)

    async def resume_session(self) -> None:
        """v2 replaces session/load with session/resume; history is replayed from the start."""
        assert self.session_id is not None, "Session id must be set"
        cwd = await self.resume_cwd()
        with self.request():
            session_resume_response = api.session_resume(
                self.session_id, cwd, [], {"type": "start"}
            )
        self._apply_session_setup(await session_resume_response.wait() or {})

    async def prompt(self, prompt: list[protocol.ContentBlock]) -> str | None:
        """Send a prompt.

        The response only acknowledges that the prompt was inserted; the turn ends
        when the agent reports an idle `state_update`.

        https://agentclientprotocol.com/protocol/v2/prompt-lifecycle
        """
        assert self.session_id is not None
        turn = self._turn = _Turn()
        self._prompt_in_flight = True
        try:
            with self.request():
                session_prompt = api.session_prompt_v2(
                    self.session_id, prompt, str(uuid.uuid4())
                )
            result = await self.wait_prompt_response(session_prompt)
        finally:
            self._prompt_in_flight = False
        if result is None:
            self._turn = None
            return None
        if message_id := result.get("messageId"):
            self._own_message_ids.add(message_id)
        turn.inserted = True
        try:
            stop_reason, error = await turn.future
        finally:
            if self._turn is turn:
                self._turn = None
        if stop_reason == "error":
            self.post_message(
                AgentFail(
                    "Agent turn failed",
                    str((error or {}).get("message", ""))
                    or f"{self.agent_name} returned an error",
                )
            )
        return stop_reason

    async def set_mode(self, mode_id: str) -> str | None:
        """Set the mode via the 'mode' config option."""
        if self._mode_config_id is None or self.session_id is None:
            return "This agent doesn't support modes"
        with self.request():
            response = api.session_set_config_option(
                self.session_id, self._mode_config_id, "id", mode_id
            )
        try:
            result = await response.wait()
        except jsonrpc.APIError as error:
            return error.message or "Failed to set mode"
        if isinstance(result, dict):
            self._apply_config_options(result.get("configOptions"))
        return None

    async def cancel(self) -> bool:
        if self.session_id is None:
            return False
        with self.request():
            api.session_cancel_v2(self.session_id)
        # session/cancel is a notification; the turn ends with an idle state_update
        return True
