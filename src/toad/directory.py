from __future__ import annotations

import asyncio
from itertools import filterfalse
from typing import Callable
from time import time
from os import PathLike
from pathlib import Path

from textual._partition import partition

from toad.path_filter import PathFilter

# Try to import Rust implementation
try:
    from toad._rust_fuzzy import scan_directory_parallel as _rust_scan
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False


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

    async def run(self) -> None:
        queue = self.queue
        results = self.results
        add_directories = self.add_directories
        while True:
            try:
                scan_path = await queue.get()
            except asyncio.QueueShutDown:
                break
            paths, dir_paths = await asyncio.to_thread(
                self._scan_directory, scan_path, self.path_filter
            )
            if add_directories:
                results.extend(dir_paths)
            results.extend(paths)
            try:
                for path in dir_paths:
                    await queue.put(path)
            except asyncio.QueueShutDown:
                break
            queue.task_done()

    def _scan_directory(
        self, root: Path, path_filter: PathFilter | None = None
    ) -> tuple[list[Path], list[Path]]:
        """Perform a directory scan (done in a thread).

        Args:
            root: Path to scan.
            path_filter: PathFilter object.

        Returns:
            A tuple of lists of paths (FILES, DIRECTORIES)
        """
        try:
            paths = list(root.iterdir())
        except IOError:
            paths = []
        if path_filter is not None:
            paths = list(filterfalse(path_filter.match, paths))

        try:
            paths, dir_paths = partition(Path.is_dir, paths)
        except IOError:
            paths = []
            dir_paths = []
        return paths, dir_paths


async def scan(
    root: Path,
    *,
    max_simultaneous: int = 5,
    path_filter: PathFilter | None = None,
    add_directories: bool = False,
    max_duration: float | None = 5.0,
) -> list[Path]:
    """Scan a directory for paths.

    Args:
        root: Root directory to scan.
        max_simultaneous: Maximum number of scan jobs.
        path_filter: Path filter object.
        add_directories: Also collect directories?
        max_duration: Maximum time in seconds to scan for, or `None` for no maximum.

    Returns:
        A list of Paths.
    """
    # Use Rust implementation if available (much faster)
    if _RUST_AVAILABLE:
        try:
            # Run Rust scan in thread
            path_strings = await asyncio.to_thread(
                _rust_scan,
                str(root),
                add_directories,
                max_duration
            )
            
            # Convert strings to Path objects
            paths = [Path(p) for p in path_strings]
            
            # Apply path filter if provided
            if path_filter is not None:
                paths = [p for p in paths if not path_filter.match(p)]
            
            return paths
        except Exception:
            # Fall back to Python implementation on any error
            pass
    
    # Python implementation (fallback)
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
        if max_duration is not None:
            try:
                async with asyncio.timeout(max_duration):
                    await queue.join()
            except asyncio.TimeoutError:
                pass
        else:
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
    import asyncio

    import contextlib
    from time import perf_counter
    from typing import Generator

    @contextlib.contextmanager
    def timer(subject: str = "time") -> Generator[None, None, None]:
        """print the elapsed time. (only used in debugging)"""
        start = perf_counter()
        yield
        elapsed = perf_counter() - start
        elapsed_ms = elapsed
        print(f"{subject} elapsed {elapsed_ms:.4f}s")

    from toad.path_filter import PathFilter

    scan_path = Path("~/projects/textual").expanduser()

    path_filter = PathFilter.from_git_root(scan_path)

    async def run():
        with timer("scan"):
            return await scan(scan_path, path_filter=path_filter)

    paths = asyncio.run(run())
    print(len(paths))
