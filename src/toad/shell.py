from __future__ import annotations


import os
import asyncio
import codecs
import fcntl
import pty
import struct
import termios
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.message import Message
from textual.widget import Widget


from toad.widgets.ansi_log import ANSILog

if TYPE_CHECKING:
    from toad.widgets.conversation import Conversation


def resize_pty(fd, cols, rows):
    """Resize the pseudo-terminal"""
    # Pack the dimensions into the format expected by TIOCSWINSZ
    size = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, size)


@dataclass
class CurrentWorkingDirectoryChanged(Message):
    path: str


class Shell:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation
        self.ansi_log: ANSILog | None = None
        self.shell = os.environ.get("SHELL", "sh")
        self.master = 0
        self._task: asyncio.Task | None = None
        self.width = 80
        self.height = 24

    async def send(self, command: str, width: int, height: int) -> None:
        self.width = width
        self.height = height
        resize_pty(self.master, width, height)
        command = f"{command}\n"
        self.writer.write(command.encode("utf-8"))

        get_pwd_command = r'printf "\e]2025;$(pwd);\e\\"' + "\n"
        self.writer.write(get_pwd_command.encode("utf-8"))
        self.ansi_log = None

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def run(self) -> None:
        master, slave = pty.openpty()
        self.master = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Get terminal attributes
        attrs = termios.tcgetattr(slave)

        # Disable echo (ECHO flag)
        attrs[3] &= ~termios.ECHO

        # Apply the changes
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TTY_COMPATIBLE"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["TOAD"] = "1"

        shell = f"{self.shell} +o interactive"
        # shell = self.shell

        process = await asyncio.create_subprocess_shell(
            shell,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
        )

        os.close(slave)

        reader = asyncio.StreamReader()
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

        current_directory = ""
        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        await asyncio.sleep(1 / 60)
        try:
            while True:
                data = await reader.read(1024 * 128)
                if line := unicode_decoder.decode(data, final=not data):
                    if self.ansi_log is None:
                        self.ansi_log = await self.conversation.get_ansi_log(self.width)
                        self.ansi_log.display = False
                    if self.ansi_log.write(line):
                        self.ansi_log.display = True
                    new_directory = self.ansi_log.current_directory
                    if new_directory != current_directory:
                        current_directory = new_directory
                        self.conversation.post_message(
                            CurrentWorkingDirectoryChanged(current_directory)
                        )
                if not data:
                    break

        finally:
            transport.close()

        await process.wait()
