import asyncio
import json
import os
from pathlib import Path

import rich.repr

from textual.content import Content
from textual.message_pump import MessagePump
from textual import log

from toad import jsonrpc
from toad.agent import AgentBase
from toad.acp import protocol
from toad.acp import api
from toad.acp.api import API
from toad.acp import messages
from toad.acp.prompt import build as build_prompt
from toad.answer import Answer

PROTOCOL_VERSION = 1


@rich.repr.auto
class Agent(AgentBase):
    """An agent that speaks the APC (https://agentclientprotocol.com/overview/introduction) protocol."""

    def __init__(self, project_root: Path, command: str) -> None:
        """

        Args:
            project_root: Project root path.
            command: Command to launch agent.
        """
        super().__init__(project_root)

        self.command = command

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
        self.session_id: str = ""

        self._message_target: MessagePump | None = None

    def __rich_repr__(self) -> rich.repr.Result:
        yield self.project_root_path
        yield self.command

    def get_info(self) -> Content:
        return Content(self.command)

    def start(self, message_target: MessagePump | None = None) -> None:
        """Start the agent."""
        self._message_target = message_target
        self._agent_task = asyncio.create_task(self._run_agent())

    def send(self, request: jsonrpc.Request) -> None:
        """Send a request to the agent.

        This is called automatically, if you go through `self.request`.

        Args:
            request: JSONRPC request object.

        """
        assert self._process is not None, "Process should be present here"
        print("SEND", request.body)
        if (stdin := self._process.stdin) is not None:
            stdin.write(b"%s\n" % request.body_json)

    def request(self) -> jsonrpc.Request:
        """Create a request object."""
        return API.request(self.send)

    @jsonrpc.expose("session/update")
    def rpc_session_update(self, sessionId: str, update: protocol.SessionUpdate):
        """Agent requests an update.

        https://agentclientprotocol.com/protocol/schema
        """
        log(update)
        message_target = self._message_target
        if message_target is None:
            return
        match update:
            case {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": type, "text": text},
            }:
                message_target.post_message(messages.ACPUpdate(type, text))
            case {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": type, "text": text},
            }:
                message_target.post_message(messages.ACPThinking(type, text))

    @jsonrpc.expose("session/request_permission")
    async def rpc_request_permission(
        self,
        sessionId: str,
        options: list[protocol.PermissionOption],
        toolCall: protocol.ToolCallUpdate,
        _meta: dict | None = None,
    ) -> protocol.RequestPermissionResponse:
        """_summary_

        Args:
            sessionId: The session ID.
            options: A list of permission options (potential replies).
            toolCall: The tool or tools the agent is requesting permission to call.
            _meta: Optional meta information.

        Returns:
            The response to the permission request.
        """
        assert self._message_target is not None
        result_future: asyncio.Future[Answer] = asyncio.Future()
        self._message_target.post_message(
            messages.ACPRequestPermission(options, toolCall, result_future)
        )
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
        print("WRITE TEXT FILE", path)
        write_path = self.project_root_path / path
        write_path.write_text(content, encoding="utf-8", errors="ignore")

    async def _run_agent(self) -> None:
        """Task to communicate with the agent subprocess."""

        agent_output = open("agent.jsonl", "wb")

        PIPE = asyncio.subprocess.PIPE
        process = self._process = await asyncio.create_subprocess_shell(
            self.command,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            env=os.environ,
        )

        self._task = asyncio.create_task(self.run())

        assert process.stdout is not None
        assert process.stdin is not None

        tasks: set[asyncio.Task] = set()

        async def call_jsonrpc(request: jsonrpc.JSONObject | jsonrpc.JSONList) -> None:
            print("calling", request)
            try:
                result = await self.server.call(request)
                print("result", result)
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
            agent_output.writelines([line])
            try:
                agent_data = json.loads(line.decode("utf-8"))
                print("IN", agent_data)
            except Exception:
                # TODO: handle this
                raise

            if isinstance(agent_data, dict):
                if "result" in agent_data or "error" in agent_data:
                    API.process_response(agent_data)
                    continue

            elif isinstance(agent_data, list):
                if not all(isinstance(datum, dict) for datum in agent_data):
                    log.warning(f"Agent sent invalid data: {agent_data!r}")
                    continue
                if all(("result" in datum or "error" in datum) for datum in agent_data):
                    API.process_response(agent_data)
                    continue

            # By this point we know it is a JSON RPC call
            print("JSONRPC CALL")
            print(agent_data)
            tasks.add(asyncio.create_task(call_jsonrpc(agent_data)))

        print("exit")

    async def run(self) -> None:
        """The main logic of the Agent."""
        # Boilerplate to initialize comms
        await self.acp_initialize()
        # Create a new session
        await self.acp_new_session()

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
            )

        response = await initialize_response.wait()
        print(response)
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
        self.session_id = response["sessionId"]

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
        return result.get("stopReason")


if __name__ == "__main__":
    from rich import print

    async def run_agent():
        agent = Agent(Path("./"), "gemini --experimental-acp")
        print(agent)
        agent.start()
        await agent.done_event.wait()

    asyncio.run(run_agent())
