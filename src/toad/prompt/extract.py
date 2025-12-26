import re2 as re
from typing import Iterable


RE_MATCH_FILE_PROMPT = re.compile(r"@(\S+)|@\"(.*)\"")


def extract_paths_from_prompt(prompt: str) -> Iterable[tuple[str, int, int]]:
    """Find file syntax in prompts.

    Args:
        prompt: A line of prompt.

    Yields:
        A tuple of (PATH, START, END).
    """
    for match in RE_MATCH_FILE_PROMPT.finditer(prompt):
        path, quoted_path = match.groups()
        yield (path or quoted_path, match.start(0), match.end(0))
