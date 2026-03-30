import asyncio
from itertools import islice
import os
from pathlib import Path
from typing import Iterable, Literal, Sequence


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
        """Read the directory contents."""
        # TODO: Arbitary limit, to avoid stalling on very large directories
        # Should this be configurable?
        try:
            for path in islice(self.path.iterdir(), None, 10_000):
                self.directory_listing.append(path)
        except OSError:
            return

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

    @classmethod
    def decorate_listing(cls, paths: Iterable[Path]) -> list[str]:
        """Add trailing slash to directories.

        Args:
            paths: A sequence of paths.

        Returns:
            A list of directory names.
        """
        return [(path.name + "/" if path.is_dir() else path.name) for path in paths]

    @classmethod
    def decorate_path(cls, path: Path) -> str:
        """Add trailing slash to a path if it is a directory.

        Args:
            path: Path.

        Returns:
            The path name, potentially with a trailing slash.
        """
        return path.name + "/" if path.is_dir() else path.name

    async def __call__(
        self,
        current_working_directory: Path,
        path: str,
        *,
        exclude_type: Literal["file"] | Literal["dir"] | None = None,
    ) -> tuple[str | None, list[str] | None]:
        """Attempt to auto-complete a path.

        Args:
            current_working_directory: Current working directory (to resolve relative paths).
            path: String potentially containing path to auto-complete.
            exclude_type: May be `"file"` to exclude files, `"dir"` to exclude directories, or `None` not to exclude anything.

        Returns:
            A pair of the recommend auto complete (or `None`), and a list of options (or `None`).
        """

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

        def check_completions(
            listing: list[Path],
        ) -> tuple[str | None, list[str] | None]:
            """Check completions from a listing (run in a thread)

            Args:
                listing: List of paths.

            Returns:
                Completions.
            """
            if exclude_type is not None:
                if exclude_type == "dir":
                    listing = [
                        listing_path
                        for listing_path in listing
                        if not listing_path.is_dir()
                    ]
                else:
                    listing = [
                        listing_path
                        for listing_path in listing
                        if listing_path.is_dir()
                    ]

            if not node:
                return None, self.decorate_listing(listing)

            node_name = Path(node).name

            if not node_name or path.endswith("/"):
                return None, self.decorate_listing(listing)
            matching_nodes = [
                listing_path
                for listing_path in listing
                if listing_path.name.startswith(node_name)
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

            complete_name = Path(path).name
            completed_prefix = prefix[len(complete_name) :]
            path_options = [
                (
                    matched_path.name[len(complete_name) :] + "/"
                    if matched_path.is_dir()
                    else matched_path.name[len(complete_name) :]
                )
                for matched_path in matching_nodes
                if matched_path.name.startswith(complete_name)
            ]

            if len(path_options) > 1:
                return None, path_options

            if picked_path.is_dir() and len(path_options) <= 1:
                completed_prefix += os.sep

            return completed_prefix or None, path_options

        return await asyncio.to_thread(check_completions, listing)


if __name__ == "__main__":

    async def run():
        path_complete = PathComplete()
        cwd = Path("~/sandbox")

        print(await path_complete(cwd, "~/p"))

    asyncio.run(run())
