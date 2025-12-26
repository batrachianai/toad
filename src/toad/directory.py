from __future__ import annotations

import asyncio
from typing import Callable
from time import time
from os import PathLike
from pathlib import Path


from toad.path_filter import PathFilter


class ScanJob:
    """A single directory scanning job."""

    def __init__(
        self,
        name: str,
        queue: asyncio.Queue[Path],
        results: list[Path],
        path_filter: PathFilter | None = None,
        add_directories=False,
    ) -> None:
        self.queue = queue
        self.results = results
        self.name = name
        self.path_filter = path_filter
        self.add_directories = add_directories

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def is_file(self, path: Path) -> bool:
        """Check if the path references a file.

        Args:
            path: A path.

        Returns:
            `True` if the path is a file, `False` if it isn't or an error occured.
        """
        try:
            return await asyncio.to_thread(path.is_file)
        except OSError:
            return False

    async def is_dir(self, path: Path) -> bool:
        """Check if the path references a directory.

        Args:
            path: A path.

        Returns:
            `True` if the path is a directory, `False` if it isn't or an error occured.
        """
        try:
            return await asyncio.to_thread(path.is_dir)
        except OSError:
            return False

    async def run(self) -> None:
        queue = self.queue
        results = self.results
        add_directories = self.add_directories
        while True:
            try:
                scan_path = await queue.get()
            except asyncio.QueueShutDown:
                break
            paths = await self._scan(scan_path)
            for path in paths:
                if self.path_filter is not None and self.path_filter.match(path):
                    continue
                if await self.is_dir(path):
                    if add_directories:
                        results.append(path)
                    await queue.put(path)
                else:
                    results.append(path)
            queue.task_done()

    async def _scan(self, root: Path) -> list[Path]:
        """Get a directory listing.

        Args:
            root: Root path.

        Returns:
            List of paths within the given directory, or empty list if an error occured.
        """

        def get_directory() -> list[Path]:
            try:
                return list(root.iterdir())
            except IOError:
                return []

        return await asyncio.to_thread(get_directory)


async def scan(
    root: Path,
    *,
    max_simultaneous: int = 10,
    path_filter: PathFilter | None = None,
    add_directories: bool = False,
) -> list[Path]:
    """Scan a directory for paths.

    Args:
        root: Root directory to scan.
        max_simultaneous: Maximum number of scan jobs.

    Returns:
        A list of Paths.
    """
    queue: asyncio.Queue[Path] = asyncio.Queue()
    results: list[Path] = []
    jobs = [
        ScanJob(
            f"scan-job #{index}",
            queue,
            results,
            path_filter=path_filter,
            add_directories=add_directories,
        )
        for index in range(max_simultaneous)
    ]
    try:
        await queue.put(root)
        for job in jobs:
            job.start()
        await queue.join()
    except asyncio.CancelledError:
        await queue.join()
    queue.shutdown(immediate=True)
    return results


class Scan:
    """A scan of a single directory."""

    def __init__(self, root: Path, on_complete: Callable[[Scan]]) -> None:
        self.root = root
        self._on_complete = on_complete
        self._complete_event = asyncio.Event()
        self._scan_result: list[Path] = []
        self._scan_task: asyncio.Task | None = None
        self._scan_time = time()

    @property
    def is_complete(self) -> bool:
        """Has the scan finished?"""
        return self._complete_event.is_set()

    def start(self) -> None:
        self._scan_time = time()
        self._scan_task = asyncio.create_task(self._run(), name=f"scan {self.root!s}")

    async def _run(self) -> None:
        await asyncio.to_thread(self._scan)
        self._complete_event.set()
        self._on_complete(self)

    def _scan(self) -> None:
        self._scan_result = list(self.root.iterdir())

    async def wait(self) -> list[Path]:
        """Get the result of the scan, potentially waiting for it to finish first.

        Returns:
            A list of paths in the root.
        """
        await self._complete_event.wait()
        assert self._scan_result is not None
        self._scan_task = None
        return self._scan_result


class DirectoryScanner:
    """Object to recursively scan a directory."""

    def __init__(self, root: PathLike) -> None:
        self.root = Path(root)
        self.directories: dict[Path, Scan] = {}

    async def scan(
        self, relative_directory_path: str, on_complete: Callable[[Scan]]
    ) -> Scan:
        """Get a scan.

        Scans are created on demand, or returned previously scanned.

        Args:
            relative_directory_path: A path relative to the root.
            on_complete: Callback when scan is complete, will be invoked with Scan instance.

        Returns:
            A scan instance.
        """
        scan_path = self.root / relative_directory_path
        if scan := self.directories.get(scan_path):
            if scan.is_complete:
                on_complete(scan)
        else:
            self.directories[scan_path] = scan = Scan(
                scan_path, on_complete=on_complete
            )
            scan.start()
        return scan


if __name__ == "__main__":
    # from rich import print

    from textual.fuzzy import Matcher

    import contextlib
    from time import perf_counter
    from typing import Generator

    @contextlib.contextmanager
    def timer(subject: str = "time") -> Generator[None, None, None]:
        """print the elapsed time. (only used in debugging)"""
        start = perf_counter()
        yield
        elapsed = perf_counter() - start
        elapsed_ms = elapsed * 1000
        print(f"{subject} elapsed {elapsed_ms:.4f}ms")

    async def run_scan():
        paths = await scan(
            Path("./"),
        )
        str_paths = [str(path) for path in paths]
        matcher = Matcher("psputils")
        results = []

        with timer("fuzzy"):
            for path in str_paths:
                score = matcher.match(path)
                if score > 0:
                    print(path)
                results.append((score, path))

        # print(results)

    asyncio.run(run_scan())
