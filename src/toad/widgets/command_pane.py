import asyncio
import codecs
from dataclasses import dataclass
from typing import Any

import os
import platform
import struct

from textual import events
from textual.message import Message

from toad.shell_read import shell_read

from toad.widgets.terminal import Terminal

IS_WINDOWS = platform.system() == "Windows"

# Platform-specific imports
WINPTY_AVAILABLE = False
PtyProcess = None

if IS_WINDOWS:
    try:
        from winpty import PtyProcess
        WINPTY_AVAILABLE = True
    except (ImportError, OSError):
        WINPTY_AVAILABLE = False
else:
    import fcntl
    import pty
    import termios


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
        self._pty_process: Any = None
        self._process: asyncio.subprocess.Process | None = None
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
        if IS_WINDOWS and WINPTY_AVAILABLE:
            if self._pty_process is None:
                return
        elif IS_WINDOWS:
            if self._process is None:
                return
        else:
            if self._master is None:
                return
        self._size_changed()

    def _size_changed(self):
        width, height = self.scrollable_content_region.size
        if IS_WINDOWS and WINPTY_AVAILABLE:
            if self._pty_process is None:
                return
            try:
                self._pty_process.setwinsize(height, width)
            except Exception:
                pass
        elif IS_WINDOWS:
            # No resize for subprocess fallback
            pass
        else:
            if self._master is None:
                return
            try:
                size = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self._master, termios.TIOCSWINSZ, size)
            except OSError:
                pass
        self.update_size(width, height)

    @property
    def is_cooked(self) -> bool:
        """Is the terminal in 'cooked' mode?"""
        if IS_WINDOWS:
            # Windows PTY doesn't have a direct equivalent
            return True
        if self._master is None:
            return True
        attrs = termios.tcgetattr(self._master)
        lflag = attrs[3]
        return bool(lflag & termios.ICANON)

    async def write_stdin(self, text: str | bytes, hide_echo: bool = False) -> int:
        if IS_WINDOWS and WINPTY_AVAILABLE:
            if self._pty_process is None:
                return 0
            text_str = text.decode("utf-8", "ignore") if isinstance(text, bytes) else text
            try:
                await asyncio.to_thread(self._pty_process.write, text_str)
                return len(text_str)
            except Exception:
                return 0
        elif IS_WINDOWS:
            if self._process is None or self._process.stdin is None:
                return 0
            text_bytes = text.encode("utf-8", "ignore") if isinstance(text, str) else text
            try:
                self._process.stdin.write(text_bytes)
                await self._process.stdin.drain()
                return len(text_bytes)
            except Exception:
                return 0
        else:
            if self._master is None:
                return 0
            text_bytes = text.encode("utf-8", "ignore") if isinstance(text, str) else text
            try:
                return await asyncio.to_thread(os.write, self._master, text_bytes)
            except OSError:
                return 0

    async def _execute(self, command: str, *, final: bool = True) -> None:
        if IS_WINDOWS and WINPTY_AVAILABLE:
            await self._execute_windows(command, final=final)
        elif IS_WINDOWS:
            await self._execute_windows_subprocess(command, final=final)
        else:
            await self._execute_unix(command, final=final)

    async def _execute_windows(self, command: str, *, final: bool = True) -> None:
        """Windows-specific command execution using pywinpty."""
        await self.wait_for_refresh()

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TOAD"] = "1"

        try:
            self._pty_process = await asyncio.to_thread(
                PtyProcess.spawn,
                command,
                env=env,
            )
        except Exception as error:
            raise CommandError(f"Failed to execute {command!r}; {error}")

        self._size_changed()

        self.set_write_to_stdin(self.write_stdin)

        BUFFER_SIZE = 64 * 1024
        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        try:
            while True:
                try:
                    data = await asyncio.to_thread(self._pty_process.read, BUFFER_SIZE)
                    if isinstance(data, str):
                        data = data.encode("utf-8", "ignore")
                except EOFError:
                    data = b""
                except Exception:
                    data = b""

                if line := unicode_decoder.decode(data, final=not data):
                    try:
                        await self.write(line)
                    except Exception as error:
                        print(repr(line))
                        print(error)
                        from traceback import print_exc
                        print_exc()

                if not data:
                    break
        finally:
            pass

        try:
            return_code = self._return_code = await asyncio.to_thread(
                self._pty_process.wait
            )
        except Exception:
            return_code = self._return_code = -1

        if final:
            self.set_class(return_code == 0, "-success")
            self.set_class(return_code != 0, "-fail")
        self.post_message(self.CommandComplete(return_code or 0))
        self.hide_cursor = True

    async def _execute_windows_subprocess(self, command: str, *, final: bool = True) -> None:
        """Windows fallback using subprocess (no PTY) when pywinpty is unavailable."""
        await self.wait_for_refresh()

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TOAD"] = "1"

        try:
            self._process = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except Exception as error:
            raise CommandError(f"Failed to execute {command!r}; {error}")

        self._size_changed()
        self.set_write_to_stdin(self.write_stdin)

        BUFFER_SIZE = 64 * 1024
        unicode_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        try:
            while True:
                if self._process.stdout is None:
                    break
                try:
                    data = await self._process.stdout.read(BUFFER_SIZE)
                except Exception:
                    data = b""

                if line := unicode_decoder.decode(data, final=not data):
                    try:
                        await self.write(line)
                    except Exception as error:
                        print(repr(line))
                        print(error)
                        from traceback import print_exc
                        print_exc()

                if not data:
                    break
        finally:
            pass

        await self._process.wait()
        return_code = self._return_code = self._process.returncode
        if final:
            self.set_class(return_code == 0, "-success")
            self.set_class(return_code != 0, "-fail")
        self.post_message(self.CommandComplete(return_code or 0))
        self.hide_cursor = True

    async def _execute_unix(self, command: str, *, final: bool = True) -> None:
        """Unix-specific command execution."""
        await self.wait_for_refresh()

        master, slave = pty.openpty()
        self._master = master

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

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
                start_new_session=True,
            )
        except Exception as error:
            raise CommandError(f"Failed to execute {command!r}; {error}")

        os.close(slave)

        self._size_changed()

        self.set_write_to_stdin(self.write_stdin)

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
                        await self.write(line)
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


if __name__ == "__main__":
    from textual.app import App, ComposeResult
    from textual.content import Content

    COMMAND = os.environ["SHELL"]
    # COMMAND = "python test_input.py"

    # COMMAND = "htop"
    # COMMAND = "python test_scroll_margins.py"

    # COMMAND = "python cpr.py"

    COMMAND = "python test_input.py"

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
            command_pane.border_title = Content(COMMAND)
            command_pane.execute(COMMAND)

    app = CommandApp()
    app.run()
