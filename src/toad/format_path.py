from pathlib import Path


def format_path(path: Path | str, directory: bool = False) -> str:
    """Format a path, using ~/ syntax as approriate.

    Args:
        path: A path in Path or str form.
        directory: Format path as a directory (append with separator).

    Returns:
        Returns a formatted path string.
    """
    if isinstance(path, str):
        path = Path(path)
    path = path.expanduser().resolve()
    try:
        relative = path.relative_to(Path.home())
        formatted_path = f"~/{relative}"
    except ValueError:
        # Path is not relative to home
        formatted_path = str(path)
    if directory and not formatted_path.endswith("/"):
        formatted_path += "/"
    return formatted_path
