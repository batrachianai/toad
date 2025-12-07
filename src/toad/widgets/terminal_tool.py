from __future__ import annotations

import asyncio
from asyncio.subprocess import Process
import codecs
import fcntl
import os
import pty
import shlex
from collections import deque
from dataclasses import dataclass
import struct
import termios
from typing import Mapping

from textual.content import Content
from textual import events
from textual.reactive import var

from toad.shell_read import shell_read
from toad.widgets.terminal import Terminal


@dataclass
class Command:
    """A command and corresponding environment."""

    command: str
    """Command to run."""
    args: list[str]
    """List of arguments."""
    env: Mapping[str, str]
    """Environment variables."""
    cwd: str
    """Current working directory."""

    def __str__(self) -> str:
        command_str = shlex.join([self.command, *self.args]).strip("'")
        return command_str


@dataclass
class ToolState:
    """Current state of the terminal."""

    output: str
    truncated: bool
    return_code: int | None = None
    signal: str | None = None


class TerminalTool(Terminal):
    DEFAULT_CSS = """
    TerminalTool {
        height: auto;
        border: panel $text-primary;
    }
    """

    _command: var[Command | None] = var(None)

    def __init__(
        self,
        command: Command,
        *,
        output_byte_limit: int | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        minimum_terminal_width: int = -1,
    ):
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            minimum_terminal_width=minimum_terminal_width,
        )
        self._command = command
        self._output_byte_limit = output_byte_limit
        self._command_task: asyncio.Task | None = None
        self._output: deque[bytes] = deque()

        self._process: Process | None = None
        self._bytes_read = 0
        self._output_bytes_count = 0
        self._shell_fd: int | None = None
        self._return_code: int | None = None
        self._released: bool = False
        self._ready_event = asyncio.Event()
        self._exit_event = asyncio.Event()

    @property
    def return_code(self) -> int | None:
        """The command return code, or `None` if not yet set."""
        return self._return_code

    @property
    def released(self) -> bool:
        """Has the terminal been released?"""
        return self._released

    @property
    def tool_state(self) -> ToolState:
        """Get the current terminal state."""
        output, truncated = self.get_output()
        # TODO: report signal
        return ToolState(
            output=output, truncated=truncated, return_code=self.return_code
        )

    @staticmethod
    def resize_pty(fd: int, columns: int, rows: int) -> None:
        """Resize the pseudo terminal.

        Args:
            fd: File descriptor.
            columns: Columns (width).
            rows: Rows (height).
        """
        # Pack the dimensions into the format expected by TIOCSWINSZ
        size = struct.pack("HHHH", rows, columns, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)

    async def wait_for_exit(self) -> tuple[int | None, str | None]:
        """Wait for the terminal process to exit."""
        if self._process is None or self._command_task is None:
            return None, None
        # await self._task
        await self._exit_event.wait()
        return (self.return_code or 0, None)

    def kill(self) -> bool:
        """Kill the terminal process.

        Returns:
            Returns `True` if the process was killed, or `False` if there
                was no running process.
        """
        if self.return_code is not None:
            return False
        if self._process is None:
            return False
        try:
            self._process.kill()
        except Exception:
            return False
        return True

    def release(self) -> None:
        """Release the terminal (may no longer be used from ACP)."""
        self._released = True

    def watch__command(self, command: Command) -> None:
        self.border_title = str(command)

    async def start(self, width: int = 0, height: int = 0) -> None:
        assert self._command is not None

        self.update_size(width, height)
        self._command_task = asyncio.create_task(
            self.run(), name=f"Terminal {self._command}"
        )
        await self._ready_event.wait()

    async def run(self) -> None:
        try:
            await self._run()
        except Exception:
            from traceback import print_exc

            print_exc()
        finally:
            self._exit_event.set()

    async def _run(self) -> None:
        self._command_task = asyncio.current_task()

        assert self._command is not None
        master, slave = pty.openpty()
        self._shell_fd = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # # Get terminal attributes
        # attrs = termios.tcgetattr(slave)

        # # Disable echo (ECHO flag)
        # attrs[3] &= ~termios.ECHO

        # # Apply the changes
        # termios.tcsetattr(slave, termios.TCSANOW, attrs)

        command = self._command
        environment = os.environ | command.env

        if " " in command.command:
            run_command = command.command
        else:
            run_command = f"{command.command} {shlex.join(command.args)}"

        shell = os.environ.get("SHELL", "sh")
        run_command = shlex.join([shell, "-c", run_command])

        try:
            process = self._process = await asyncio.create_subprocess_shell(
                run_command,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=environment,
                cwd=command.cwd,
            )
        except Exception as error:
            self._ready_event.set()
            print(error)
            raise

        self._ready_event.set()

        self.resize_pty(
            master,
            self._width or 80,
            self._height or 24,
        )

        os.close(slave)
        BUFFER_SIZE = 64 * 1024 * 2
        reader = asyncio.StreamReader(BUFFER_SIZE)
        protocol = asyncio.StreamReaderProtocol(reader)

        loop = asyncio.get_event_loop()
        transport, _ = await loop.connect_read_pipe(
            lambda: protocol, os.fdopen(master, "rb", 0)
        )
        # Create write transport
        writer_protocol = asyncio.BaseProtocol()
        write_transport, _ = await loop.connect_write_pipe(
            lambda: writer_protocol,
            os.fdopen(os.dup(master), "wb", 0),
        )
        self.writer = write_transport

        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                data = await shell_read(reader, BUFFER_SIZE)
                if process_data := unicode_decoder.decode(data, final=not data):
                    self._record_output(data)
                    if self.write(process_data):
                        self.display = True
                if not data:
                    break
        finally:
            transport.close()

        self.finalize()
        return_code = self._return_code = await process.wait()

        if return_code == 0:
            self.add_class("-success")
        else:
            self.add_class("-error")
            self.border_title = Content.assemble(
                f"{command} [{return_code}]",
            )

    def _record_output(self, data: bytes) -> None:
        """Keep a record of the bytes left.

        Store at most the limit set in self._output_byte_limit (if set).

        """

        self._output.append(data)
        self._output_bytes_count += len(data)
        self._bytes_read += len(data)

        if self._output_byte_limit is None:
            return

        while self._output_bytes_count > self._output_byte_limit and self._output:
            oldest_bytes = self._output[0]
            oldest_bytes_count = len(oldest_bytes)
            if self._output_bytes_count - oldest_bytes_count < self._output_byte_limit:
                break
            self._output.popleft()
            self._output_bytes_count -= oldest_bytes_count

    def get_output(self) -> tuple[str, bool]:
        """Get the output.

        Returns:
            A tuple of the output and a bool to indicate if the output was truncated.
        """
        output_bytes = b"".join(self._output)

        def is_continuation(byte_value: int) -> bool:
            """Check if the given byte is a utf-8 continuation byte.

            Args:
                byte_value: Ordinal of the byte.

            Returns:
                `True` if the byte is a continuation, or `False` if it is the start of a character.
            """
            return (byte_value & 0b11000000) == 0b10000000

        truncated = False
        if (
            self._output_byte_limit is not None
            and len(output_bytes) > self._output_byte_limit
        ):
            truncated = True
            output_bytes = output_bytes[-self._output_byte_limit :]
            # Must start on a utf-8 boundary
            # Discard initial bytes that aren't a utf-8 continuation byte.
            for offset, byte_value in enumerate(output_bytes):
                if not is_continuation(byte_value):
                    if offset:
                        output_bytes = output_bytes[offset:]
                    break

        output = output_bytes.decode("utf-8", "replace")
        return output, truncated


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    command = Command("python", ["mandelbrot.py"], os.environ.copy(), os.curdir)

    class TApp(App):
        CSS = """
        Terminal.-success  {
            border: panel $text-success 90%;
        }
        """

        def compose(self) -> ComposeResult:
            yield TerminalTool(command)

        def on_mount(self) -> None:
            self.query_one(TerminalTool).start()

    TApp().run()
