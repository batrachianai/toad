import asyncio
import os
from pathlib import Path
from typing import Literal


def longest_common_prefix(strings: list[str]) -> str:
    """
    Find the longest common prefix among a list of strings.

    Arguments:
        strings: List of strings

    Returns:
        The longest common prefix string
    """
    if not strings:
        return ""

    # Start with the first string as reference
    prefix: str = strings[0]

    # Compare with each subsequent string
    for current_string in strings[1:]:
        # Reduce prefix until it matches the start of current string
        while not current_string.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""

    return prefix


class DirectoryReadTask:
    """A task to read a directory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.done_event = asyncio.Event()
        self.directory_listing: list[Path] = []
        self._task: asyncio.Task | None = None

    def read(self) -> None:
        # TODO: Should this be cancellable, or have a maximum number of paths for the case of very large directories?
        for path in self.path.iterdir():
            self.directory_listing.append(path)

    def start(self) -> None:
        self._task = asyncio.create_task(
            self.run(), name=f"DirectoryReadTask({str(self.path)!r})"
        )

    async def run(self):
        try:
            await asyncio.to_thread(self.read)
        finally:
            self.done_event.set()

    async def wait(self) -> list[Path]:
        await self.done_event.wait()
        return self.directory_listing


class PathComplete:
    """Auto completes paths."""

    def __init__(self) -> None:
        self.read_tasks: dict[Path, DirectoryReadTask] = {}
        self.directory_listings: dict[Path, list[Path]] = {}

    async def __call__(
        self,
        current_working_directory: Path,
        path: str,
        *,
        exclude_type: Literal["file"] | Literal["dir"] | None = None,
    ) -> tuple[str | None, list[str] | None]:
        current_working_directory = (
            current_working_directory.expanduser().resolve().absolute()
        )
        directory_path = (current_working_directory / Path(path).expanduser()).resolve()

        node: str = path
        if not directory_path.is_dir():
            node = directory_path.name
            directory_path = directory_path.parent

        if (listing := self.directory_listings.get(directory_path)) is None:
            read_task = DirectoryReadTask(directory_path)
            self.read_tasks[directory_path] = read_task
            read_task.start()
            listing = await read_task.wait()

        if exclude_type is not None:
            if exclude_type == "dir":
                listing = [
                    listing_path
                    for listing_path in listing
                    if not listing_path.is_dir()
                ]
            else:
                listing = [
                    listing_path for listing_path in listing if listing_path.is_dir()
                ]

        if not node:
            return None, [listing_path.name for listing_path in listing]

        matching_nodes = [
            listing_path
            for listing_path in listing
            if listing_path.name.startswith(node)
        ]
        if not (matching_nodes):
            # Nothing matches
            return None, None

        if not (
            prefix := longest_common_prefix(
                [node_path.name for node_path in matching_nodes]
            )
        ):
            return None, None

        picked_path = directory_path / prefix
        path_size = (
            len(str(Path(directory_path).expanduser().resolve())) + 1 + len(node)
        )
        completed_prefix = str(picked_path)[path_size:]
        path_options = [
            str(path)[path_size + len(completed_prefix) :] for path in matching_nodes
        ]
        path_options = [name for name in path_options if name]

        if picked_path.is_dir() and not path_options:
            completed_prefix += os.sep

        return completed_prefix or None, path_options


if __name__ == "__main__":

    async def run():
        path_complete = PathComplete()
        cwd = Path("~/sandbox")

        print(await path_complete(cwd, "~/p"))

    asyncio.run(run())
