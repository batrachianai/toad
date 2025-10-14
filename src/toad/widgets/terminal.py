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
import sys
import termios
from typing import Mapping

from textual.reactive import var

from toad.widgets.ansi_log import ANSILog


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
        return shlex.join([self.command, *self.args])


@dataclass
class TerminalState:
    """Current state of the terminal."""

    output: str
    truncated: bool
    return_code: int | None = None
    signal: str | None = None


class Terminal(ANSILog):
    DEFAULT_CSS = """
    Terminal {
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
        self._task: asyncio.Task | None = None
        self._output: deque[bytes] = deque()

        self._process: Process | None = None
        self._bytes_read = 0
        self._output_bytes_count = 0
        self._shell_fd: int | None = None
        self._return_code: int | None = None
        self._released: bool = False
        self._exit_event = asyncio.Event()

        self._width: int | None = None
        self._height: int | None = None

    @property
    def return_code(self) -> int | None:
        """The command return code, or `None` if not yet set."""
        return self._return_code

    @property
    def released(self) -> bool:
        """Has the terminal been released?"""
        return self._released

    @property
    def state(self) -> TerminalState:
        """Get the current terminal state."""
        output, truncated = self.get_output()
        # TODO: report signal
        return TerminalState(
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
        if self._process is None:
            return None, None
        self.notify("waiting")
        await self._exit_event.wait()
        self.notify(f"done {self.return_code}")
        assert self.return_code is not None
        return (self.return_code, None)

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

    def start(self, width: int = 0, height: int = 0) -> None:
        assert self._command is not None
        self._width = width or 80
        self._height = height or 80
        self._task = asyncio.create_task(self.run())

    async def run(self) -> None:
        try:
            await self._run()
        except Exception as error:
            from traceback import print_exc

            print_exc()

    async def _run(self) -> None:
        assert self._command is not None
        master, slave = pty.openpty()
        self._shell_fd = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Get terminal attributes
        attrs = termios.tcgetattr(slave)

        # Disable echo (ECHO flag)
        attrs[3] &= ~termios.ECHO

        # Apply the changes
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

        command = self._command

        run_command, *args = shlex.split(command.command.strip("'"))
        process_args = [*args, *command.args]
        environment = os.environ | command.env

        if " " in command.command:
            run_command = command.command
        else:
            run_command = f"{command.command} {shlex.join(command.args)}"

        shell = os.environ.get("SHELL", "sh")
        run_command = shlex.join([shell, "-c", run_command])
        print("RUN", run_command)

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
            print(error)
            raise

        self.resize_pty(master, self._width or 80, self._height or 24)

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

        # self.writer.write(f"{run_command}\n".encode("utf-8"))

        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                data = await reader.read(BUFFER_SIZE)
                print(repr(data))
                if process_data := unicode_decoder.decode(data, final=not data):
                    self._record_output(data)
                    print(repr(process_data))
                    if self.write(process_data):
                        self.display = True
                if not data:
                    break
        finally:
            transport.close()

        await process.wait()
        self._return_code = process.returncode
        self._exit_event.set()

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
        def compose(self) -> ComposeResult:
            yield Terminal(command)

        def on_mount(self) -> None:
            self.query_one(Terminal).start()

    TApp().run()
