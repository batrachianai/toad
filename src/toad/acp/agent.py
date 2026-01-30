import asyncio

from contextlib import suppress
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, cast, NamedTuple
from copy import deepcopy

import rich.repr

from textual.content import Content
from textual.message import Message
from textual.message_pump import MessagePump

from toad import jsonrpc
import toad
from toad.agent_schema import Agent as AgentData
from toad.agent import AgentBase, AgentReady, AgentFail
from toad.acp import protocol
from toad.acp import api
from toad.acp.api import API
from toad.acp import messages
from toad.acp.prompt import build as build_prompt
from toad.db import DB
from toad import paths
from toad import constants
from toad.answer import Answer

PROTOCOL_VERSION = 1


class Mode(NamedTuple):
    """An agent mode."""

    id: str
    name: str
    description: str | None


def generate_datetime_filename(
    prefix: str, suffix: str, datetime_format: str | None = None
) -> str:
    """Generate a filename which includes the current date and time.

    Useful for ensuring a degree of uniqueness when saving files.

    Args:
        prefix: Prefix to attach to the start of the filename, before the timestamp string.
        suffix: Suffix to attach to the end of the filename, after the timestamp string.
            This should include the file extension.
        datetime_format: The format of the datetime to include in the filename.
            If None, the ISO format will be used.
    """
    if datetime_format is None:
        dt = datetime.now().isoformat()
    else:
        dt = datetime.now().strftime(datetime_format)

    file_name_stem = f"{prefix} {dt}"
    for reserved in ' <>:"/\\|?*.':
        file_name_stem = file_name_stem.replace(reserved, "_")
    return file_name_stem + suffix


@rich.repr.auto
class Agent(AgentBase):
    """An agent that speaks the APC (https://agentclientprotocol.com/overview/introduction) protocol."""

    def __init__(
        self, project_root: Path, agent: AgentData, session_id: str | None
    ) -> None:
        """

        Args:
            project_root: Project root path.
            command: Command to launch agent.
        """
        super().__init__(project_root)

        self._agent_data = agent
        self.session_id = session_id

        self.server = jsonrpc.Server()
        self.server.expose_instance(self)

        self._agent_task: asyncio.Task | None = None
        self._task: asyncio.Task | None = None
        self._process: asyncio.subprocess.Process | None = None
        self.done_event = asyncio.Event()

        self.agent_capabilities: protocol.AgentCapabilities = {
            "loadSession": False,
            "promptCapabilities": {
                "audio": False,
                "embeddedContent": False,
                "image": False,
            },
        }
        self.auth_methods: list[protocol.AuthMethod] = []

        self.session_pk: int | None = None
        self.tool_calls: dict[str, protocol.ToolCall] = {}
        self._message_target: MessagePump | None = None

        self._terminal_count: int = 0

        log_filename: str = generate_datetime_filename(f"{agent['name']}", ".txt")
        if log_path := os.environ.get("TOAD_LOG"):
            self._log_file_path = Path(log_path).resolve().absolute()
            with suppress(OSError):
                self._log_file_path.unlink(missing_ok=True)
        else:
            self._log_file_path = paths.get_log() / log_filename

    @property
    def command(self) -> str | None:
        """The command used to launch the agent, or `None` if there isn't one."""
        acp_command = toad.get_os_matrix(self._agent_data["run_command"])
        return acp_command

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.project_root_path
        yield self.command

    def log(self, line: str) -> None:
        """Write text to the agent log file.

        Args:
            line: Text to be logged.

        """
        if self._message_target is not None:
            self._message_target.call_later(self._log, line)

    async def _log(self, line: str) -> None:
        """Write text to the agent log file.

        Intended to be called from `log`

        Args:
            line: Text to be logged.
        """

        if self._message_target is None:
            return

        def write_log(log_file_path: Path, line: str):
            """Write log in a thread."""
            try:
                with log_file_path.open("at") as log_file:
                    log_file.write(f"{line.rstrip()}\n")
            except OSError:
                pass

        await asyncio.to_thread(write_log, self._log_file_path, line)

    def get_info(self) -> Content:
        agent_name = self._agent_data["name"]
        return Content(agent_name)

    def start(self, message_target: MessagePump | None = None) -> None:
        """Start the agent."""
        self._message_target = message_target
        try:
            self._log_file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._agent_task = asyncio.create_task(self._run_agent())

    def send(self, request: jsonrpc.Request) -> None:
        """Send a request to the agent.

        This is called automatically, if you go through `self.request`.

        Args:
            request: JSONRPC request object.

        """
        assert self._process is not None, "Process should be present here"

        self.log(f"[client] {request.body}")
        if (stdin := self._process.stdin) is not None:
            stdin.write(b"%s\n" % request.body_json)

    def request(self) -> jsonrpc.Request:
        """Create a request object."""
        return API.request(self.send)

    def post_message(self, message: Message) -> bool:
        """Post a message to the message target (the Conversation).

        Args:
            message: Message object.

        Returns:
            `True` if the message was posted successfully, or `False` if it wasn't.
        """
        if (message_target := self._message_target) is None:
            return False
        return message_target.post_message(message)

    @jsonrpc.expose("session/update")
    def rpc_session_update(
        self,
        sessionId: str,
        update: protocol.SessionUpdate,
        _meta: dict[str, Any] | None = None,
    ):
        """Agent requests an update.

        https://agentclientprotocol.com/protocol/schema
        """
        status_line: str | None = None
        if _meta and (field_meta := _meta.get("field_meta")) is not None:
            if (
                open_hands_metrics := field_meta.get("openhands.dev/metrics")
            ) is not None:
                status_line = open_hands_metrics.get("status_line")

        match update:
            case {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": type, "text": text},
            }:
                self.post_message(messages.Update(type, text))

            case {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": type, "text": text},
            }:
                self.post_message(messages.Thinking(type, text))

            case {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_call_id,
            }:
                self.tool_calls[tool_call_id] = update
                self.post_message(messages.ToolCall(update))

            case {"sessionUpdate": "plan", "entries": entries}:
                self.post_message(messages.Plan(entries))

            case {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_call_id,
            }:
                if tool_call_id in self.tool_calls:
                    current_tool_call = self.tool_calls[tool_call_id]
                    for key, value in update.items():
                        if value is not None:
                            current_tool_call[key] = value

                    self.post_message(
                        messages.ToolCallUpdate(deepcopy(current_tool_call), update)
                    )
                else:
                    # The agent can send a tool call update, without previously sending the tool call *rolls eyes*
                    current_tool_call: protocol.ToolCall = {
                        "sessionUpdate": "tool_call",
                        "toolCallId": tool_call_id,
                        "title": "Tool call",
                    }
                    for key, value in update.items():
                        if value is not None:
                            current_tool_call[key] = value

                    self.tool_calls[tool_call_id] = current_tool_call
                    self.post_message(messages.ToolCall(current_tool_call))

            case {
                "sessionUpdate": "available_commands_update",
                "availableCommands": available_commands,
            }:
                self.post_message(messages.AvailableCommandsUpdate(available_commands))

            case {"sessionUpdate": "current_mode_update", "currentModeId": mode_id}:
                self.post_message(messages.ModeUpdate(mode_id))

        if status_line is not None:
            self.post_message(messages.UpdateStatusLine(status_line))

    @jsonrpc.expose("session/request_permission")
    async def rpc_request_permission(
        self,
        sessionId: str,
        options: list[protocol.PermissionOption],
        toolCall: protocol.ToolCallUpdatePermissionRequest,
        _meta: dict | None = None,
    ) -> protocol.RequestPermissionResponse:
        """Agent requests permission to make a tool call.

        Args:
            sessionId: The session ID.
            options: A list of permission options (potential replies).
            toolCall: The tool or tools the agent is requesting permission to call.
            _meta: Optional meta information.

        Returns:
            The response to the permission request.
        """
        result_future: asyncio.Future[Answer] = asyncio.Future()
        tool_call_id = toolCall["toolCallId"]

        permission_tool_call = toolCall.copy()
        permission_tool_call.pop("sessionUpdate", None)
        tool_call = cast(protocol.ToolCall, permission_tool_call)
        if tool_call_id in self.tool_calls:
            self.tool_calls[tool_call_id] |= tool_call
        else:
            self.tool_calls[tool_call_id] = deepcopy(tool_call)

        tool_call = deepcopy(self.tool_calls[tool_call_id])

        message = messages.RequestPermission(options, tool_call, result_future)
        self.post_message(message)
        await result_future
        ask_result = result_future.result()

        request_permission_outcome: protocol.OutcomeSelected = {
            "optionId": ask_result.id,
            "outcome": "selected",
        }
        result: protocol.RequestPermissionResponse = {
            "outcome": request_permission_outcome
        }
        return result

    @jsonrpc.expose("fs/read_text_file")
    def rpc_read_text_file(
        self,
        sessionId: str,
        path: str,
        line: int | None = None,
        limit: int | None = None,
    ) -> dict[str, str]:
        """Read a file in the project."""
        # TODO: what if the read is outside of the project path?
        # https://agentclientprotocol.com/protocol/file-system#reading-files
        read_path = self.project_root_path / path
        try:
            text = read_path.read_text(encoding="utf-8", errors="ignore")
        except IOError:
            text = ""
        if line is not None:
            line = max(0, line - 1)
            if limit is None:
                text = "\n".join(text.splitlines()[line:])
            else:
                text = "\n".join(text.splitlines()[line : line + limit])
        return {"content": text}

    @jsonrpc.expose("fs/write_text_file")
    def rpc_write_text_file(self, sessionId: str, path: str, content: str) -> None:
        # TODO: What if the agent wants to write outside of the project path?
        # https://agentclientprotocol.com/protocol/file-system#writing-files

        write_path = self.project_root_path / path
        write_path.write_text(content, encoding="utf-8", errors="ignore")

    # https://agentclientprotocol.com/protocol/schema#createterminalrequest
    @jsonrpc.expose("terminal/create")
    async def rpc_terminal_create(
        self,
        command: str,
        _meta: dict | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[protocol.EnvVariable] | None = None,
        outputByteLimit: int | None = None,
        sessionId: str | None = None,
    ) -> protocol.CreateTerminalResponse:
        # Assign a terminal id
        self._terminal_count = self._terminal_count + 1
        terminal_id = f"terminal-{self._terminal_count}"

        terminal_env = (
            {variable["name"]: variable["value"] for variable in env} if env else {}
        )
        result_future: asyncio.Future[bool] = asyncio.Future()
        self.post_message(
            messages.CreateTerminal(
                terminal_id,
                command=command,
                args=args,
                cwd=cwd,
                env=terminal_env,
                output_byte_limit=outputByteLimit,
                result_future=result_future,
            )
        )
        await result_future
        if not result_future.result():
            raise jsonrpc.JSONRPCError("Failed to create a terminal.")
        return {"terminalId": terminal_id}

    # https://agentclientprotocol.com/protocol/schema#killterminalcommandrequest
    @jsonrpc.expose("terminal/kill")
    def rpc_terminal_kill(
        self, sessionID: str, terminalId: str, _meta: dict | None = None
    ) -> protocol.KillTerminalCommandResponse:
        self.post_message(messages.KillTerminal(terminalId))
        return {}

    # https://agentclientprotocol.com/protocol/schema#terminal%2Foutput
    @jsonrpc.expose("terminal/output")
    async def rpc_terminal_output(
        self, sessionId: str, terminalId: str, _meta: dict | None = None
    ) -> protocol.TerminalOutputResponse:
        from toad.widgets.terminal_tool import ToolState

        result_future: asyncio.Future[ToolState] = asyncio.Future()

        if not self.post_message(messages.GetTerminalState(terminalId, result_future)):
            raise RuntimeError("Unable to get terminal output")

        await result_future
        terminal_state = result_future.result()

        result: protocol.TerminalOutputResponse = {
            "output": terminal_state.output,
            "truncated": terminal_state.truncated,
        }
        if (return_code := terminal_state.return_code) is not None:
            result["exitStatus"] = {"exitCode": return_code}
        return result

    # https://agentclientprotocol.com/protocol/schema#terminal%2Frelease
    @jsonrpc.expose("terminal/release")
    def rpc_terminal_release(
        self, sessionId: str, terminalId: str, _meta: dict | None = None
    ) -> protocol.ReleaseTerminalResponse:
        self.post_message(messages.ReleaseTerminal(terminalId))
        return {}

    # https://agentclientprotocol.com/protocol/schema#terminal%2Fwait-for-exit
    @jsonrpc.expose("terminal/wait_for_exit")
    async def rpc_terminal_wait_for_exit(
        self, sessionId: str, terminalId: str, _meta: dict | None = None
    ) -> protocol.WaitForTerminalExitResponse:
        result_future: asyncio.Future[tuple[int, str | None]] = asyncio.Future()
        if not self.post_message(
            messages.WaitForTerminalExit(terminalId, result_future)
        ):
            raise RuntimeError("Unable to wait for terminal exit; no terminal found")

        await result_future
        return_code, signal = result_future.result()
        return {"exitCode": return_code, "signal": signal}

    async def _run_agent(self) -> None:
        """Task to communicate with the agent subprocess."""

        PIPE = asyncio.subprocess.PIPE
        env = os.environ.copy()
        env["TOAD_CWD"] = str(Path("./").absolute())

        if (command := self.command) is None:
            self.post_message(
                AgentFail("Failed to start agent; no run command for this OS")
            )
            return

        try:
            process = self._process = await asyncio.create_subprocess_shell(
                command,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                env=env,
                cwd=str(self.project_root_path),
                limit=10 * 1024 * 1024,
            )
        except Exception as error:
            self.post_message(AgentFail("Failed to start agent", details=str(error)))
            return

        self._task = asyncio.create_task(self.run())

        assert process.stdout is not None
        assert process.stdin is not None

        tasks: set[asyncio.Task] = set()

        async def call_jsonrpc(request: jsonrpc.JSONObject | jsonrpc.JSONList) -> None:
            try:
                if (result := await self.server.call(request)) is not None:
                    result_json = json.dumps(result).encode("utf-8")
                    if process.stdin is not None:
                        process.stdin.write(b"%s\n" % result_json)
            finally:
                if (task := asyncio.current_task()) is not None:
                    tasks.discard(task)

        while line := await process.stdout.readline():
            # This line should contain JSON, which may be:
            #   A) a JSONRPC request
            #   B) a JSONRPC response to a previous request
            if not line.strip():
                continue

            try:
                line_str = line.decode("utf-8")
            except Exception as error:
                self.log(f"[error] Unable to decode utf-8 from agent: {error}")
                continue

            self.log(f"[agent] {line_str}")
            try:
                agent_data: jsonrpc.JSONType = json.loads(line_str)
            except Exception as error:
                self.log(f"[error] failed to decode JSON from agent: {error}")
                continue

            if isinstance(agent_data, dict):
                if "result" in agent_data or "error" in agent_data:
                    API.process_response(agent_data)
                    continue

            elif isinstance(agent_data, list):
                if not all(isinstance(datum, dict) for datum in agent_data):
                    self.log(f"[error] Agent sent invalid data: {agent_data!r}")
                    continue
                if all(
                    isinstance(datum, dict) and ("result" in datum or "error" in datum)
                    for datum in agent_data
                ):
                    API.process_response(agent_data)
                    continue

            if not isinstance(agent_data, dict):
                self.log("[error] Invalid JSON from agent {agent_data!r}")
                continue

            # By this point we know it is a JSON RPC call
            assert isinstance(agent_data, dict)
            tasks.add(asyncio.create_task(call_jsonrpc(agent_data)))

        if process.returncode:
            assert process.stderr is not None
            fail_details = (await process.stderr.read()).decode("utf-8", "replace")
            self.post_message(
                AgentFail(
                    f"Agent returned a failure code: [b]{process.returncode}",
                    details=fail_details,
                )
            )

        self._process = None

    async def stop(self) -> None:
        """Gracefully stop the process."""
        if self.session_pk is not None:
            db = DB()
            await db.session_update_last_used(self.session_pk)

        if self._process is not None:
            self._process.terminate()

    async def run(self) -> None:
        """The main logic of the Agent."""
        if constants.ACP_INITIALIZE:
            try:
                # Boilerplate to initialize comms
                await self.acp_initialize()

                if self.session_id is None:
                    # Create a new session
                    await self.acp_new_session()
                else:
                    # Load existing session
                    if not self.agent_capabilities.get("loadSession", False):
                        self.post_message(
                            AgentFail(
                                "Resume not supported",
                                f"{self._agent_data['name']} does not currently support resuming sessions.",
                                help="no_resume",
                            )
                        )
                        return
                    await self.acp_load_session()
            except jsonrpc.APIError as error:
                if isinstance(error.data, dict):
                    reason = str(
                        error.data.get("reason") or "Failed to initialize agent"
                    )
                    details = str(
                        error.data.get("details") or error.data.get("error") or ""
                    )
                else:
                    reason = "Failed to initialize agent"
                    details = ""
                self.post_message(AgentFail(reason, details))

        self.post_message(AgentReady())

    async def send_prompt(self, prompt: str) -> str | None:
        """Send a prompt to the agent.

        !!! note
            This method blocks as it may defer to a thread to read resources.

        Args:
            prompt: Prompt text.
        """
        prompt_content_blocks = await asyncio.to_thread(
            build_prompt, self.project_root_path, prompt
        )
        return await self.acp_session_prompt(prompt_content_blocks)

    async def acp_initialize(self):
        """Initialize agent."""
        with self.request():
            initialize_response = api.initialize(
                PROTOCOL_VERSION,
                {
                    "fs": {
                        "readTextFile": True,
                        "writeTextFile": True,
                    },
                    "terminal": True,
                },
                {
                    "name": toad.NAME,
                    "title": toad.TITLE,
                    "version": toad.get_version(),
                },
            )

        response = await initialize_response.wait()
        assert response is not None

        # Store agents capabilities
        if agent_capabilities := response.get("agentCapabilities"):
            self.agent_capabilities = agent_capabilities
        if auth_methods := response.get("authMethods"):
            self.auth_methods = auth_methods

    async def acp_new_session(self) -> None:
        """Create a new session."""
        with self.request():
            session_new_response = api.session_new(
                str(self.project_root_path),
                [],
            )
        response = await session_new_response.wait()
        assert response is not None
        self.session_id = response["sessionId"]

        db = DB()
        self.session_pk = await db.session_new(
            "New Session",
            self._agent_data["name"],
            self._agent_data["identity"],
            self.session_id,
            protocol="acp",
        )

        if (modes := response.get("modes", None)) is not None:
            current_mode = modes["currentModeId"]
            available_modes = modes["availableModes"]
            modes_update = {
                mode["id"]: Mode(
                    mode["id"], mode["name"], mode.get("description", None)
                )
                for mode in available_modes
            }
            self.post_message(messages.SetModes(current_mode, modes_update))

    async def acp_load_session(self) -> None:
        assert self.session_id is not None, "Session id must be set"
        with self.request():
            session_load_response = api.session_load(
                str(self.project_root_path), [], self.session_id
            )
        response = await session_load_response.wait()

        if (modes := response.get("modes", None)) is not None:
            current_mode = modes["currentModeId"]
            available_modes = modes["availableModes"]
            modes_update = {
                mode["id"]: Mode(
                    mode["id"], mode["name"], mode.get("description", None)
                )
                for mode in available_modes
            }
            self.post_message(messages.SetModes(current_mode, modes_update))

    async def acp_session_prompt(
        self, prompt: list[protocol.ContentBlock]
    ) -> str | None:
        """Send the prompt to the agent.

        Returns:
            The stop reason.

        """
        with self.request():
            session_prompt = api.session_prompt(prompt, self.session_id)
        result = await session_prompt.wait()
        assert result is not None
        return result.get("stopReason")

    async def acp_session_set_mode(self, mode_id: str) -> str | None:
        """Update the current mode with the agent."""
        with self.request():
            response = api.session_set_mode(self.session_id, mode_id)
        try:
            await response.wait()
        except jsonrpc.APIError as error:
            match error.data:
                case {"details": details}:
                    return details if isinstance(details, str) else "Failed to set mode"
            return "Failed to set mode"
        else:
            return None

    async def set_mode(self, mode_id: str) -> str | None:
        return await self.acp_session_set_mode(mode_id)

    async def set_session_name(self, name: str) -> None:
        if self.session_pk is None:
            return
        db = DB()
        await db.session_update_title(self.session_pk, name)

    async def acp_session_cancel(self) -> bool:
        with self.request():
            response = api.session_cancel(self.session_id, {})
        try:
            await response.wait()
        except jsonrpc.APIError:
            # No-op if there is nothing to cancel
            return False
        return True

    async def cancel(self) -> bool:
        return await self.acp_session_cancel()
