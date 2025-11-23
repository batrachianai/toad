import asyncio
import codecs
from dataclasses import dataclass

import os
import fcntl
import pty
import struct
import termios


from textual.message import Message

from toad.shell_read import shell_read

# from toad.widgets.ansi_log import ANSILog
from toad.widgets.terminal import Terminal


class CommandError(Exception):
    """An error occurred running the command."""


class CommandPane(Terminal):
    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        self._execute_task: asyncio.Task | None = None
        self._return_code: int | None = None
        super().__init__(name=name, id=id, classes=classes)

    @property
    def return_code(self) -> int | None:
        return self._return_code

    @dataclass
    class CommandComplete(Message):
        return_code: int

    def execute(self, command: str) -> None:
        self._execute_task = asyncio.create_task(self._execute(command))

    async def _execute(self, command: str) -> None:
        width, height = self.scrollable_content_region.size

        master, slave = pty.openpty()

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Get terminal attributes
        attrs = termios.tcgetattr(slave)

        # Disable echo (ECHO flag)
        attrs[3] &= ~termios.ECHO
        attrs[0] |= termios.ISIG

        # Apply the changes
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TTY_COMPATIBLE"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["TOAD"] = "1"
        env["CLICOLOR"] = "1"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                start_new_session=True,  # Linux / macOS only
            )
        except Exception as error:
            raise CommandError(f"Failed to execute {command!r}; {error}")

        os.close(slave)

        size = struct.pack("HHHH", height, width, 0, 0)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)

        BUFFER_SIZE = 64 * 1024
        reader = asyncio.StreamReader(BUFFER_SIZE)
        protocol = asyncio.StreamReaderProtocol(reader)

        loop = asyncio.get_event_loop()
        transport, _ = await loop.connect_read_pipe(
            lambda: protocol, os.fdopen(master, "rb", 0)
        )

        # Create write transport
        writer_protocol = asyncio.BaseProtocol()
        self.write_transport, _ = await loop.connect_write_pipe(
            lambda: writer_protocol,
            os.fdopen(os.dup(master), "wb", 0),
        )
        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        from textual._profile import timer

        try:
            while True:
                data = await shell_read(reader, BUFFER_SIZE)
                if line := unicode_decoder.decode(data, final=not data):
                    with timer("write"):
                        self.write(line)
                if not data:
                    break
        finally:
            transport.close()

        await process.wait()
        return_code = self._return_code = process.returncode
        self.set_class(return_code == 0, "-success")
        self.set_class(return_code != 0, "-fail")
        self.post_message(self.CommandComplete(return_code or 0))
        self.hide_cursor = True

    def write_stdin(self, stdin_bytes: bytes) -> None:
        self.write_transport.write(stdin_bytes)

    def write_process_stdin(self, input: str) -> None:
        stdin_bytes = input.encode("utf-8")
        self.write_transport.write(stdin_bytes)


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    COMMAND = """htop"""
    # COMMAND = "uv run python -m textual"
    COMMAND = "uv run python"

    COMMAND = "uv run textual keys"
    # COMMAND = "uv run python test_scroll1.py"

    COMMAND = "uv run python test_scroll_region.py"

    COMMAND = "uv run python test_scroll_margins.py"

    COMMAND = "htop"
    # COMMAND = "uv run python test_ind.py"
    # COMMAND = "nano"
    # COMMAND = "uv run textual keys"

    class CommandApp(App):
        CSS = """
        Screen {
            align: center middle;
        }
        CommandPane {
            # background: blue 20%;
            scrollbar-gutter: stable;
            background: black 10%;
            max-height: 40;
            # border: green;
            border: tab $text-primary;            
            margin: 0 2;
        }
        """

        def compose(self) -> ComposeResult:
            yield CommandPane()

        def on_mount(self) -> None:
            command_pane = self.query_one(CommandPane)
            command_pane.border_title = COMMAND
            self.call_after_refresh(command_pane.execute, COMMAND)

    app = CommandApp()
    app.run()
