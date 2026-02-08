import asyncio
import itertools
import threading
from pathlib import Path

from textual.cache import LRUCache
from textual.suggester import Suggester


class ListDirCache:
    """A cache for listing a directory (not a Rich / Textual object).

    This class is responsible for listing directories, and caching the results.

    Listing a directory is a blocking operation, which is why we defer the work to a thread.

    """

    def __init__(self) -> None:
        self._cache: LRUCache[tuple[str, int], list[Path]] = LRUCache(100)
        self._lock = threading.Lock()

    async def listdir(self, path: Path, size: int) -> list[Path]:
        cache_key = (str(path), size)

        def iterdir_thread(path: Path) -> list[Path]:
            """Run iterdir in a thread.

            Returns:
                A list of paths.
            """
            return list(itertools.islice(path.iterdir(), size))

        with self._lock:
            if cache_key in self._cache:
                paths = self._cache[cache_key]
            else:
                paths = await asyncio.to_thread(iterdir_thread, path)
                self._cache[cache_key] = paths
            return paths


class DirectorySuggester(Suggester):
    """Suggest a directory.

    This is a [Suggester](https://textual.textualize.io/api/suggester/#textual.suggester.Suggester) instance,
    used by the Input widget to suggest auto-completions.

    """

    def __init__(self) -> None:
        self._cache = ListDirCache()
        super().__init__(case_sensitive=True)

    async def get_suggestion(self, value: str) -> str | None:
        """Suggest the first matching directory."""

        try:
            path = Path(value)
            name = path.name

            children = await self._cache.listdir(
                path.expanduser() if path.is_dir() else path.parent.expanduser(), 100
            )
            possible_paths = [
                f"{sibling_path}/"
                for sibling_path in children
                if sibling_path.name.lower().startswith(name.lower())
                and sibling_path.is_dir()
            ]
            if possible_paths:
                possible_paths.sort(key=str.__len__)
                suggestion = possible_paths[0]

                if "~" in value:
                    home = str(Path("~").expanduser())
                    suggestion = suggestion.replace(home, "~", 1)
                return suggestion

        except FileNotFoundError:
            pass
        return None


if __name__ == "__main__":
    from textual.app import App, ComposeResult
    from textual import widgets

    class SApp(App):
        def compose(self) -> ComposeResult:
            yield widgets.Input(suggester=DirectorySuggester())

    SApp().run()
