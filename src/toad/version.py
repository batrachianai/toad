from typing import NamedTuple


class VersionMeta(NamedTuple):
    """Information about the current version of Canon."""

    version: str
    upgrade_message: str
    visit_url: str


class VersionCheckFailed(Exception):
    """Something went wrong in the version check."""


async def check_version() -> tuple[bool, VersionMeta]:
    """Check for a new version of Canon.

    The upstream Toad version check contacted batrachian.ai, which is not
    applicable to the Canon fork. This stub always reports no update
    available so callers continue to work without modification.

    Returns:
        A tuple of (update_available=False, current VersionMeta).
    """
    from toad import get_version

    meta = VersionMeta(
        version=get_version(),
        upgrade_message="",
        visit_url="https://github.com/DEGAorg/canon-tui",
    )
    return False, meta
