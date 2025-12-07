from __future__ import annotations


from contextlib import suppress
import os
import asyncio
import codecs
import fcntl
import platform
import pty
import struct
import termios
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.message import Message

from toad.shell_read import shell_read

from toad.widgets.terminal import Terminal

if TYPE_CHECKING:
    from toad.widgets.conversation import Conversation

IS_MACOS = platform.system() == "Darwin"


def resize_pty(fd, cols, rows):
    """Resize the pseudo-terminal"""
    # Pack the dimensions into the format expected by TIOCSWINSZ
    try:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except OSError:
        # Possibly file descriptor closed
        pass


@dataclass
class CurrentWorkingDirectoryChanged(Message):
    """Current working directory has changed in shell."""

    path: str


@dataclass
class ShellFinished(Message):
    """The shell finished."""


class Shell:
    """Responsible for shell interactions in Conversation."""

    def __init__(
        self,
        conversation: Conversation,
        working_directory: str,
        shell="",
        start="",
    ) -> None:
        self.conversation = conversation
        self.working_directory = working_directory

        self.terminal: Terminal | None = None
        self.new_log: bool = False
        self.shell = shell or os.environ.get("SHELL", "sh")
        self.shell_start = start
        self.master = 0
        self._task: asyncio.Task | None = None
        self._process: asyncio.subprocess.Process | None = None
        self.writer: asyncio.WriteTransport | None = None

        self._finished: bool = False
        self._ready_event: asyncio.Event = asyncio.Event()

    @property
    def is_finished(self) -> bool:
        return self._finished

    async def send(self, command: str, width: int, height: int) -> None:
        await self._ready_event.wait()
        assert self.writer is not None

        resize_pty(self.master, width, max(height, 1))

        old_settings = termios.tcgetattr(self.master)

        # Disable echo
        new_settings = termios.tcgetattr(self.master)
        new_settings[3] = new_settings[3] & ~termios.ECHO  # lflag is at index 3
        termios.tcsetattr(self.master, termios.TCSADRAIN, new_settings)

        get_pwd_command = f"{command};" + r'printf "\e]2025;$(pwd);\e\\"' + "\n"
        self.writer.write(get_pwd_command.encode("utf-8"))

        termios.tcsetattr(self.master, termios.TCSADRAIN, old_settings)

        self.terminal = None

    def start(self) -> None:
        assert self._task is None
        self._task = asyncio.create_task(self.run(), name=repr(self))

    async def interrupt(self) -> None:
        """Interrupt the running command."""
        if self.writer is not None:
            self.writer.write(b"\x03")

    def update_size(self, width: int, height: int) -> None:
        """Update the size of the shell pty.

        Args:
            width: Desired width.
            height: Desired height.
        """
        with suppress(OSError):
            resize_pty(self.master, width, max(height, 1))

    async def run(self) -> None:
        current_directory = self.working_directory

        master, slave = pty.openpty()
        self.master = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TTY_COMPATIBLE"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["TOAD"] = "1"
        env["CLICOLOR"] = "1"

        shell = self.shell

        def setup_pty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        try:
            _process = await asyncio.create_subprocess_shell(
                shell,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                cwd=current_directory,
                preexec_fn=setup_pty,
            )
        except Exception as error:
            self.conversation.notify(
                f"Unable to start shell: {error}\n\nCheck your settings.",
                title="Shell",
                severity="error",
            )
            return

        os.close(slave)
        BUFFER_SIZE = 64 * 1024
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

        if shell_start := self.shell_start.strip():
            # Get terminal attributes

            old_settings = termios.tcgetattr(self.master)
            new_settings = termios.tcgetattr(self.master)
            new_settings[3] = new_settings[3] & ~termios.ECHO  # lflag is at index 3
            termios.tcsetattr(self.master, termios.TCSADRAIN, new_settings)

            shell_start = self.shell_start.strip()
            if not shell_start.endswith("\n"):
                shell_start += "\n"
            self.writer.write(shell_start.encode("utf-8"))

            termios.tcsetattr(slave, termios.TCSADRAIN, old_settings)

        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def write_stdin(input: str) -> None:
            if self.writer is not None:
                self.writer.write(input.encode("utf-8"))

        self._ready_event.set()
        try:
            while True:
                data = await shell_read(reader, BUFFER_SIZE)

                if line := unicode_decoder.decode(data, final=not data):
                    if self.terminal is None or self.terminal.is_finalized:
                        previous_state = (
                            None if self.terminal is None else self.terminal.state
                        )
                        self.terminal = await self.conversation.new_terminal()
                        # if previous_state is not None:
                        #     self.terminal.set_state(previous_state)
                        self.terminal.set_write_to_stdin(write_stdin)
                    if self.terminal.write(line):
                        self.terminal.display = True
                    new_directory = self.terminal.current_directory
                    if new_directory and new_directory != current_directory:
                        current_directory = new_directory
                        self.conversation.post_message(
                            CurrentWorkingDirectoryChanged(current_directory)
                        )
                if not data:
                    break

        finally:
            transport.close()
        self.writer = None
        self._finished = True
        self.conversation.post_message(ShellFinished())
