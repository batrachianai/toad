import asyncio
import codecs
from dataclasses import dataclass

import os
import fcntl
import pty
import struct
import termios


from textual import events
from textual.message import Message

from toad.shell_read import shell_read

from toad.widgets.terminal import Terminal


class CommandError(Exception):
    """An error occurred running the command."""


class CommandPane(Terminal):
    DEFAULT_CSS = """
    CommandPane {
        scrollbar-size: 0 0;

    }

    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        self._execute_task: asyncio.Task | None = None
        self._return_code: int | None = None
        self._master: int | None = None
        super().__init__(name=name, id=id, classes=classes)

    @property
    def return_code(self) -> int | None:
        return self._return_code

    @dataclass
    class CommandComplete(Message):
        return_code: int

    def execute(self, command: str, *, final: bool = True) -> asyncio.Task:
        self._execute_task = asyncio.create_task(self._execute(command, final=final))
        self.anchor()
        return self._execute_task

    def on_resize(self, event: events.Resize):
        event.prevent_default()
        if self._master is None:
            return
        self._size_changed()

    def _size_changed(self):
        if self._master is None:
            return
        width, height = self.scrollable_content_region.size
        try:
            size = struct.pack("HHHH", height, width, 0, 0)
            fcntl.ioctl(self._master, termios.TIOCSWINSZ, size)
        except OSError:
            pass
        self.update_size(width, height)

    @property
    def is_cooked(self) -> bool:
        """Is the terminal in 'cooked' mode?"""
        if self._master is None:
            return True
        attrs = termios.tcgetattr(self._master)
        lflag = attrs[3]
        return bool(lflag & termios.ICANON)

    async def _execute(self, command: str, *, final: bool = True) -> None:
        # width, height = self.scrollable_content_region.size

        await self.wait_for_refresh()

        master, slave = pty.openpty()
        self._master = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # # Get terminal attributes
        # attrs = termios.tcgetattr(slave)

        # # Apply the changes
        # termios.tcsetattr(slave, termios.TCSANOW, attrs)

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

        self._size_changed()

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
        try:
            while True:
                data = await shell_read(reader, BUFFER_SIZE)
                if line := unicode_decoder.decode(data, final=not data):
                    try:
                        self.write(line)
                    except Exception as error:
                        print(repr(line))
                        print(error)
                        from traceback import print_exc

                        print_exc()

                if not data:
                    break
        finally:
            transport.close()

        await process.wait()
        return_code = self._return_code = process.returncode
        if final:
            self.set_class(return_code == 0, "-success")
            self.set_class(return_code != 0, "-fail")
        self.post_message(self.CommandComplete(return_code or 0))
        self.hide_cursor = True

    def write_process_stdin(self, input: str) -> None:
        stdin_bytes = input.encode("utf-8")
        self.write_transport.write(stdin_bytes)


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    COMMAND = os.environ["SHELL"]
    # COMMAND = "python test_input.py"

    # COMMAND = "htop"
    # COMMAND = "python test_scroll_margins.py"

    COMMAND = "python cpr.py"

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
        # CommandPane {
        #     width: 1fr;
        #     height: 1fr;
        #     # background: black 10%;
        #     # color: white;
        #     background: ansi_default;
        #     # color: ansi_default;
        # }
        """

        def compose(self) -> ComposeResult:
            yield CommandPane()

        def on_mount(self) -> None:
            command_pane = self.query_one(CommandPane)
            command_pane.border_title = COMMAND
            command_pane.execute(COMMAND)

    app = CommandApp()
    app.run()
