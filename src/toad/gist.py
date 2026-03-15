import httpx


# This doesn't work anonymously
# TODO: Implement login
def create_gist(
    files: dict[str, str],
    description: str = "",
    public: bool = True,
) -> str:
    """Create a GitHub Gist and return its URL.

    Args:
        files: A mapping of filename to file content.
        description: An optional description for the gist.
        public: Whether the gist should be public.

    Returns:
        The URL of the created gist.
    """
    payload = {
        "description": description,
        "public": public,
        "files": {name: {"content": content} for name, content in files.items()},
    }

    response = httpx.post(
        "https://api.github.com/gists",
        json=payload,
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    return response.json()["html_url"]
