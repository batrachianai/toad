from pathlib import Path
from typing import Iterable

import asyncio

from textual import work
from textual.binding import Binding
from textual.widgets import DirectoryTree
from textual.widgets.directory_tree import DirEntry

from toad.path_filter import PathFilter


class ProjectDirectoryTree(DirectoryTree):
    BINDINGS = [
        Binding(
            "ctrl+c",
            "dismiss",
            "Interrupt",
            tooltip="Interrupt running command",
            show=False,
        ),
        Binding("ctrl+r", "refresh", "Refresh", tooltip="Refresh file view", show=True),
    ]

    def __init__(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        self._path_filter: PathFilter | None = None
        path = Path(path).resolve() if isinstance(path, str) else path.resolve()
        super().__init__(path, name=name, id=id, classes=classes, disabled=disabled)

    async def watch_path(self) -> None:
        """Watch for changes to the `path` of the directory tree.

        If the path is changed the directory tree will be repopulated using
        the new value as the root.
        """
        has_cursor = self.cursor_node is not None
        self.reset_node(self.root, str(self.path), DirEntry(self.PATH(self.path)))
        await self.reload()
        if has_cursor:
            self.cursor_line = 0
        self.scroll_to(0, 0, animate=False)

    async def on_mount(self) -> None:
        path = Path(self.path) if isinstance(self.path, str) else self.path
        path = path.resolve()
        self._path_filter = await asyncio.to_thread(PathFilter.from_git_root, path)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter the paths before adding them to the tree.

        Args:
            paths: The paths to be filtered.

        Returns:
            The filtered paths.

        By default this method returns all of the paths provided. To create
        a filtered `DirectoryTree` inherit from it and implement your own
        version of this method.
        """

        if (path_filter := self._path_filter) is not None:
            for path in paths:
                if not path_filter.match(path):
                    yield path
        else:
            yield from paths

    @work
    async def action_refresh(self) -> None:
        await self.reload()
        self.notify("Project directory has been refreshed", title="Directory Tree")
