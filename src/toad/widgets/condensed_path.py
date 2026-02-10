from functools import lru_cache
import os.path
from typing import Iterable

from rich.cells import cell_len
from textual.geometry import Size
from textual.reactive import reactive
from textual.content import Content
from textual.widget import Widget


def radiate_range(total: int) -> Iterable[tuple[int, int]]:
    """Generate pairs of indexes, gradually growing from the center.

    Args:
        total: Total size of range.

    Yields:
        Pairs of indexes.
    """
    if not total:
        return
    left = right = total // 2
    yield (left, right)
    while left >= 0 or right < total:
        left -= 1
        if left >= 0:
            yield (left + 1, right)
        right += 1
        if right <= total:
            yield (left + 1, right)


@lru_cache(maxsize=16)
def condense_path(path: str, width: int, *, prefix: str = "") -> str:
    """Condense a path to fit within the given cell width.

    Args:
        path: The path to condense.
        width: Maximum cell width.
        prefix: A string to be prepended to the result.

    Returns:
        A condensed string.
    """
    # TODO: handle OS separators and path issues
    if cell_len(path) <= width:
        return path
    components = path.split("/")
    condensed = components
    trailing_slash = path.endswith("/")
    candidate = prefix + "/".join(condensed)
    if trailing_slash and candidate and not candidate.endswith("/"):
        candidate += "/"

    for left, right in radiate_range(len(components)):
        if cell_len(candidate) < width:
            return candidate
        condensed = [*components[:left], "…", *components[right:]]
        candidate = prefix + "/".join(condensed)
        if trailing_slash and candidate and not candidate.endswith("/"):
            candidate += "/"

    return candidate


class CondensedPath(Widget):
    path = reactive("")
    display_path = reactive("")

    DEFAULT_CSS = """
    CondensedPath {
        height: 1;
    }
    """

    def __init__(
        self, path: str = "", *, id: str | None = None, classes: str | None = None
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.path = path

    def on_resize(self) -> None:
        self.watch_path(self.path)

    def watch_path(self, path: str) -> None:
        if not path or not self.size:
            return
        path = os.path.abspath(path)
        self.tooltip = str(path)
        user_root = os.path.abspath(os.path.expanduser("~/"))
        if not user_root.endswith("/"):
            user_root += "/"
        if path.startswith(user_root):
            path = "~/" + path[len(user_root) :]
        self.display_path = path

    def render(self) -> Content:
        return Content(condense_path(self.display_path, self.size.width))

    def get_content_width(self, container: Size, viewport: Size) -> int:
        if self.display_path:
            return Content(self.display_path).cell_length
        else:
            return container.width
