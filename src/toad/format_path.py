from pathlib import Path


def format_path(path: Path | str) -> str:
    """Format a path, using ~/ syntax as approriate.

    Args:
        path: A path in Path or str form.

    Returns:
        Returns a formatted path string.
    """
    if isinstance(path, str):
        path = Path(path)
    path = path.expanduser().resolve()
    home = Path.home()
    try:
        relative = path.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        # Path is not relative to home
        return str(path)
