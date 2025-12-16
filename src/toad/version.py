from typing import NamedTuple


VERSION_TOML_URL = "https://www.batrachian.ai/toad.toml"


class VersionMeta(NamedTuple):
    """Information about the current version of Toad."""

    version: str
    upgrade_message: str
    visit_url: str


class VersionCheckFailed(Exception):
    """Something went wrong in the version check."""


async def check_version() -> tuple[bool, VersionMeta]:
    """Check for a new version of Toad.

    Returns:
        A tuple containing a boolean that indicates if there is a newer version,
            and a `VersionMeta` structure with meta information.
    """
    import httpx
    import packaging.version
    import tomllib

    from toad import get_version

    try:
        current_version = packaging.version.parse(get_version())
    except packaging.version.InvalidVersion as error:
        raise VersionCheckFailed(f"Invalid version;{error}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(VERSION_TOML_URL)
            version_toml_bytes = await response.aread()
    except Exception as error:
        raise VersionCheckFailed(f"Failed to retrieve version;{error}")

    try:
        version_toml = version_toml_bytes.decode("utf-8", "replace")
        version_meta = tomllib.loads(version_toml)
    except Exception as error:
        raise VersionCheckFailed(f"Failed to decode version TOML;{error}")

    if not isinstance(version_meta, dict):
        raise VersionCheckFailed("Response isn't TOML")

    toad_version = str(version_meta.get("version", "0"))
    version_message = str(version_meta.get("upgrade_message", ""))
    version_message = version_message.replace("$VERSION", toad_version)
    verison_meta = VersionMeta(
        version=toad_version,
        upgrade_message=version_message,
        visit_url=str(version_meta.get("visit_url", "")),
    )

    try:
        new_version = packaging.version.parse(verison_meta.version)
    except packaging.version.InvalidVersion as error:
        raise VersionCheckFailed(f"Invalid remote version;{error}")

    return new_version > current_version, verison_meta


if __name__ == "__main__":

    async def run() -> None:
        result = await check_version()
        from rich import print

        print(result)

    import asyncio

    asyncio.run(run())
