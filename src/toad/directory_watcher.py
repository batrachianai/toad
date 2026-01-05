from pathlib import Path
import rich.repr

import threading

from textual.message import Message
from textual.widget import Widget


from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver


class DirectoryChanged(Message):
    """The directory was changed."""

    def can_replace(self, message: Message) -> bool:
        return isinstance(message, DirectoryChanged)


@rich.repr.auto
class DirectoryWatcher(threading.Thread, FileSystemEventHandler):
    """Watch for changes to a directory, ignoring purely file data changes."""

    def __init__(self, path: Path, widget: Widget) -> None:
        """

        Args:
            path: Root path to monitor.
            widget: Widget which will receive the `DirectoryChanged` event.
        """
        self._path = path
        self._widget = widget
        self._stop_event = threading.Event()
        self._enabled = False
        super().__init__(name=repr(self))

    @property
    def enabled(self) -> bool:
        """Is the DirectoryWatcher currently watching?"""
        return self._enabled

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Send DirectoryChanged event when the FS is updated."""
        self._widget.post_message(DirectoryChanged())

    def __rich_repr__(self) -> rich.repr.Result:
        yield self._path
        yield self._widget

    def run(self) -> None:
        try:
            observer = Observer()
        except Exception:
            return
        if isinstance(observer, PollingObserver):
            return
        try:
            observer.schedule(
                self,
                str(self._path),
                recursive=True,
                event_filter=[
                    FileCreatedEvent,
                    FileDeletedEvent,
                    FileMovedEvent,
                    DirCreatedEvent,
                    DirDeletedEvent,
                    DirMovedEvent,
                ],
            )
            observer.start()
        except Exception:
            return
        self._enabled = True
        while not self._stop_event.wait(1):
            pass
        try:
            observer.stop()
        except Exception:
            pass

    def stop(self) -> None:
        """Stop the watcher."""

        self._stop_event.set()
