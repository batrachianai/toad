from functools import lru_cache
from typing import Sequence
import re


from toad.fuzzy import FuzzySearch


class PathFuzzySearch(FuzzySearch):
    @classmethod
    @lru_cache(maxsize=1024)
    def get_first_letters(cls, candidate: str) -> frozenset[int]:
        return frozenset(
            {
                0,
                *[match.start() + 1 for match in re.finditer(r"/", candidate)],
            }
        )

    def score(self, candidate: str, positions: Sequence[int]) -> float:
        """Score a search.

        Args:
            search: Search object.

        Returns:
            Score.
        """
        first_letters = self.get_first_letters(candidate)
        # This is a heuristic, and can be tweaked for better results
        # Boost first letter matches
        offset_count = len(positions)
        score: float = offset_count + len(first_letters.intersection(positions))

        # if 0 in first_letters:
        #     score += 1

        groups = 1
        last_offset, *offsets = positions
        for offset in offsets:
            if offset != last_offset + 1:
                groups += 1
            last_offset = offset

        # Boost to favor less groups

        normalized_groups = (offset_count - (groups - 1)) / offset_count
        score *= 1 + (normalized_groups * normalized_groups)

        if positions[0] > candidate.rfind("/"):
            score *= 2
        return score
