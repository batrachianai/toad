from __future__ import annotations

import asyncio
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


class Terminal(ANSILog):
    DEFAULT_CSS = """
    Terminal {
    
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

        self._bytes_read = 0
        self._output_bytes_count = 0
        self._shell_fd: int | None = None

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

    def watch__command(self, command: Command) -> None:
        self.border_title = str(command)

    def start(self) -> None:
        assert self._command is not None
        self._task = asyncio.create_task(self.run())

    async def run(self) -> None:
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

        process = await asyncio.create_subprocess_shell(
            command.command,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=command.env,
            cwd=command.cwd,
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
                data = await reader.read(BUFFER_SIZE)
                self._record_output(data)
                if line := unicode_decoder.decode(data, final=not data):
                    if self.write(line):
                        self.display = True
                if not data:
                    break
        finally:
            transport.close()

        await process.wait()

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
            if self._output_bytes_count - oldest_bytes_count <= self._output_byte_limit:
                break
            self._output.popleft()
            self._output_bytes_count -= oldest_bytes_count

    def get_output(self) -> str:
        """Get the output.

        Returns:
            Output (may be partial if there is an output byte limit).
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

        if self._output_byte_limit is not None:
            # Discard initial bytes that aren't a utf-8 continuation byte.
            for offset, byte_value in enumerate(output_bytes):
                if not is_continuation(byte_value):
                    if offset:
                        output_bytes = output_bytes[offset:]
                    break

        output = output_bytes.decode("utf-8", "replace")
        return output
