from itertools import chain
from typing import Iterable, Sequence
from pathlib import Path
import pathspec
import pathspec.patterns
from pathspec import GitIgnoreSpec

import rich.repr


def load_path_spec(git_ignore_path: Path) -> GitIgnoreSpec | None:
    """Get a path spec instance if there is a .gitignore file present.

    Args:
        git_ignore_path): Path to .gitignore.

    Returns:
        A `PathSpec` instance.
    """
    try:
        if git_ignore_path.is_file():
            try:
                spec_text = git_ignore_path.read_text(encoding="utf-8")
            except Exception:
                # Permissions, encoding issue?
                return None
            spec = GitIgnoreSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern, spec_text.splitlines()
            )
            return spec
    except OSError:
        return None
    return None


@rich.repr.auto
class PathFilter:
    """Filter paths according to .gitignore files."""

    def __init__(
        self, root: Path, path_specs: Iterable[GitIgnoreSpec] | None = None
    ) -> None:
        self._root = root
        self._default_specs = [] if path_specs is None else list(path_specs)
        self._path_specs: dict[Path, Sequence[GitIgnoreSpec]] = {}

    def __rich_repr__(self) -> rich.repr.Result:
        yield str(self._root)

    @classmethod
    def from_git_root(cls, path: Path) -> PathFilter:
        """Load all path specs from parent directories up to the most recent directory with .git

        Args:
            path: A directory path.

        Returns:
            PathFilter instance.
        """
        filter_root = path
        path_specs: list[GitIgnoreSpec] = []
        try:
            while (parent := path.parent) != parent:
                if (path_spec := load_path_spec(path / ".gitignore")) is not None:
                    path_specs.append(path_spec)
                if (path / ".git").is_dir():
                    break
                path = parent
        except OSError:
            pass
        return PathFilter(filter_root, reversed(path_specs))

    def get_path_specs(self, path: Path) -> Sequence[GitIgnoreSpec]:
        """Get a sequence of path specs applicable to the give path.

        This will inherit path specs up to the root path of the filtr.

        Args:
            path: A directory path

        Returns:
            A sequence of path specs.
        """
        if (cached_path_specs := self._path_specs.get(path)) is not None:
            return cached_path_specs
        path_spec = load_path_spec(path / ".gitignore")
        if path == self._root:
            path_specs = [path_spec] if path_spec is not None else []
        else:
            parent_path_specs = self.get_path_specs(path.parent)
            path_specs = (
                parent_path_specs
                if path_spec is None
                else [*parent_path_specs, path_spec]
            )
        self._path_specs[path] = path_specs
        return path_specs

    def match(self, path: Path) -> bool:
        """Match a path againt the path filter.

        Returns:
            `True` if the path should be removed, `False` if it should be included.
        """
        if path.name == ".git":
            return True
        path_specs = self.get_path_specs(path.parent)
        for path_spec in chain(self._default_specs, path_specs):
            if path_spec.match_file(path):
                return True
        return False


if __name__ == "__main__":
    path_filter = PathFilter.from_git_root(Path("."))

    for path in Path(".").iterdir():
        print(path_filter.match(path), path)
    print(path_filter)
