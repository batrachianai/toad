import asyncio

from contextlib import suppress
from datetime import datetime
import json
import os
from pathlib import Path
import rich.repr

from textual.content import Content
from textual.message import Message
from textual.message_pump import MessagePump


from toad import jsonrpc
import toad
from toad.agent_schema import Agent as AgentData
from toad.agent import AgentBase, AgentReady, AgentFail
from toad.acp.api import API
from toad.acp.handshake import DEFAULT_VERSION, SUPPORTED_VERSIONS, negotiate
from toad.acp.prompt import build as build_prompt
from toad.acp.session import Session
from toad.acp.session_v1 import SessionV1
from toad.acp.session_v2 import SessionV2
from toad.db import DB
from toad import paths
from toad import constants

SESSION_TYPES: dict[int, type[Session]] = {
    SessionV1.PROTOCOL_VERSION: SessionV1,
    SessionV2.PROTOCOL_VERSION: SessionV2,
}
"""Session implementations, by negotiated protocol version."""
assert set(SESSION_TYPES) == set(SUPPORTED_VERSIONS)


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
    """An agent that speaks the APC (https://agentclientprotocol.com/overview/introduction) protocol.

    The agent manages the process and transport. After the handshake negotiates a
    protocol version, everything protocol-specific is delegated to a `Session`.
    """

    def __init__(
        self,
        project_root: Path,
        agent: AgentData,
        session_id: str | None,
        session_pk: int | None = None,
    ) -> None:
        """

        Args:
            project_root: Project root path.
            agent: Agent data.
            session_id: Session id to resume, or `None` for a new session.
            session_pk: Primary key of the session to resume.
        """
        super().__init__(project_root)

        self._agent_data = agent
        self._session_id = session_id
        self._session_pk = session_pk

        self.server = jsonrpc.Server()
        self.session: Session | None = None
        """The protocol session, created after the handshake."""
        self._session_ready = asyncio.Event()

        self._agent_task: asyncio.Task | None = None
        self._task: asyncio.Task | None = None
        self._process: asyncio.subprocess.Process | None = None
        self.done_event = asyncio.Event()

        self._message_target: MessagePump | None = None

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

    @property
    def protocol_version(self) -> int | None:
        """The negotiated protocol version, or `None` before the handshake."""
        return None if self.session is None else self.session.PROTOCOL_VERSION

    @property
    def session_pk(self) -> int | None:
        """Primary key of the session in the database, if it was saved."""
        return self._session_pk if self.session is None else self.session.session_pk

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

    async def start(self, message_target: MessagePump | None = None) -> None:
        """Start the agent."""
        self._message_target = message_target
        try:
            await asyncio.to_thread(
                self._log_file_path.parent.mkdir, parents=True, exist_ok=True
            )
        except OSError:
            pass
        self._agent_task = asyncio.create_task(self._run_agent())

    def send(self, request: jsonrpc.Request) -> None:
        """Send a request to the agent.

        This is called automatically, if you go through `self.request`.

        Args:
            request: JSONRPC request object.

        """
        if self._process is None:
            self.log("[error] Agent process isnt running")
            return

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

    def _open_session(
        self, session_type: type[Session], initialize_response: dict
    ) -> Session:
        """Create the session for the negotiated protocol, and expose its methods."""
        session = self.session = session_type(
            self,
            self._agent_data,
            self.project_root_path,
            initialize_response,
            self._session_id,
            self._session_pk,
        )
        self.server.expose_instance(session)
        self._session_ready.set()
        return session

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
                # The agent's requests are handled by the session, which exists
                # once the protocol version has been negotiated.
                await self._session_ready.wait()
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
            await asyncio.sleep(0)

        # Cancel all remaining tasks and wait for them to finish
        for task in tasks:
            task.cancel()

        # Wait for all tasks to complete cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if self.session is not None:
            self.session.connection_lost()

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
            try:
                self._process.terminate()
            except OSError:
                pass

    async def run(self) -> None:
        """The main logic of the Agent."""
        if not constants.ACP_INITIALIZE:
            # No handshake (e.g. replaying a log); assume the default version
            self._open_session(SESSION_TYPES[DEFAULT_VERSION], {})
            self.post_message(AgentReady())
            return
        try:
            # Boilerplate to initialize comms
            requested = self._agent_data.get("acp_version", DEFAULT_VERSION)
            if requested not in SUPPORTED_VERSIONS:
                self._notify(
                    f"ACP v{requested} isn't supported; using v{DEFAULT_VERSION}.",
                    title="ACP version",
                )
                requested = DEFAULT_VERSION
            handshake = await negotiate(self, requested)
            if handshake.fell_back:
                self._notify(
                    f"{self._agent_data['name']} doesn't support "
                    f"ACP v{handshake.requested}; using v{handshake.version}.",
                    title="ACP version",
                )
            session = self._open_session(
                SESSION_TYPES[handshake.version], handshake.response
            )

            if self._session_id is None:
                # Create a new session
                await session.new_session()
            else:
                # Load existing session
                if not session.supports_resume:
                    self.post_message(
                        AgentFail(
                            "Resume not supported",
                            f"{self._agent_data['name']} does not currently support resuming sessions.",
                            help="no_resume",
                        )
                    )
                    return
                await session.resume_session()
                if session.session_pk is not None:
                    db = DB()
                    await db.session_update_last_used(session.session_pk)
        except jsonrpc.APIError as error:
            if isinstance(error.data, dict):
                reason = str(error.data.get("reason") or "Failed to initialize agent")
                details = str(
                    error.data.get("details") or error.data.get("error") or ""
                )
            else:
                reason = "Failed to initialize agent"
                details = ""
            self.post_message(AgentFail(reason, details))

        self.post_message(AgentReady())

    def _notify(self, message: str, title: str = "") -> None:
        """Show a notification, if the message target supports it."""
        if (notify := getattr(self._message_target, "notify", None)) is not None:
            notify(message, title=title)

    async def send_prompt(self, prompt: str) -> str | None:
        """Send a prompt to the agent.

        !!! note
            This method blocks as it may defer to a thread to read resources.

        Args:
            prompt: Prompt text.
        """
        if self.session is None:
            return None
        prompt_content_blocks = await asyncio.to_thread(
            build_prompt, self.project_root_path, prompt
        )
        return await self.session.prompt(prompt_content_blocks)

    async def set_mode(self, mode_id: str) -> str | None:
        if self.session is None:
            return "Agent is not ready"
        return await self.session.set_mode(mode_id)

    async def set_session_name(self, name: str) -> None:
        if self.session_pk is None:
            return
        db = DB()
        await db.session_update_title(self.session_pk, name)

    async def cancel(self) -> bool:
        if self.session is None:
            return False
        return await self.session.cancel()
