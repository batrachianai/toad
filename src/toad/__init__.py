from typing import Literal, Mapping
import platform

NAME = "toad"
TITLE = "Toad by Will McGugan"

type OS = Literal["linux", "macos", "windows", "*"]

_system = platform.system()
_OS_map: dict[str, OS] = {
    "Linux": "linux",
    "Darwin": "macos",
    "Windows": "windows",
}
os: OS = _OS_map.get(_system, "linux")


def get_os_matrix(matrix: Mapping[OS, str]) -> str | None:
    """Get a value from a mapping where the key is an OS, falling back to a wildcard ("*").

    Args:
        matrix: A mapping where an OS literal is the key.

    Returns:
        The value, if one is found, or `None`.
    """
    if (result := matrix.get(os)) is None:
        result = matrix.get("*")
    return result


def get_version() -> str:
    """Get the current version of Toad.

    Returns:
        str: Version string, e.g "1.2.3"
    """
    from importlib.metadata import version

    return version("toad")
