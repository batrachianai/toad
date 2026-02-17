"""
Fuzzy matcher.

This class is used by the [command palette](/guide/command_palette) to match search terms.

"""

from __future__ import annotations

from functools import lru_cache
from operator import itemgetter
from re2 import finditer
from typing import Iterable, Sequence


from textual.cache import LRUCache

# Try to import the Rust implementation for better performance
try:
    from toad._rust_fuzzy import FuzzySearch as _RustFuzzySearch
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False


class _PythonFuzzySearch:
    """Performs a fuzzy search.

    Unlike a regex solution, this will finds all possible matches.
    """

    def __init__(
        self, case_sensitive: bool = False, *, cache_size: int = 1024 * 4, path_mode: bool = False
    ) -> None:
        """Initialize fuzzy search.

        Args:
            case_sensitive: Is the match case sensitive?
            cache_size: Number of queries to cache.
            path_mode: If True, treat '/' as word boundaries instead of word character boundaries.
        """

        self.case_sensitive = case_sensitive
        self.path_mode = path_mode
        self.cache: LRUCache[tuple[str, str], tuple[float, Sequence[int]]] = LRUCache(
            cache_size
        )

    def match(self, query: str, candidate: str) -> tuple[float, Sequence[int]]:
        """Match against a query.

        Args:
            query: The fuzzy query.
            candidate: A candidate to check,.

        Returns:
            A pair of (score, tuple of offsets). `(0, ())` for no result.
        """

        cache_key = (query, candidate)
        if cache_key in self.cache:
            return self.cache[cache_key]
        default: tuple[float, Sequence[int]] = (0.0, [])
        result = max(self._match(query, candidate), key=itemgetter(0), default=default)
        self.cache[cache_key] = result
        return result

    @classmethod
    @lru_cache(maxsize=1024)
    def get_first_letters(cls, candidate: str) -> frozenset[int]:
        return frozenset({match.start() for match in finditer(r"\w+", candidate)})
    
    @classmethod
    @lru_cache(maxsize=1024)
    def get_first_letters_path(cls, candidate: str) -> frozenset[int]:
        """Get first letters at path boundaries (after '/' characters)."""
        return frozenset(
            {
                0,
                *[match.start() + 1 for match in finditer(r"/", candidate)],
            }
        )

    def score(self, candidate: str, positions: Sequence[int]) -> float:
        """Score a search.

        Args:
            search: Search object.

        Returns:
            Score.
        """
        if self.path_mode:
            first_letters = self.get_first_letters_path(candidate)
        else:
            first_letters = self.get_first_letters(candidate)
        
        # This is a heuristic, and can be tweaked for better results
        # Boost first letter matches
        offset_count = len(positions)
        score: float = offset_count + len(first_letters.intersection(positions))

        groups = 1
        last_offset, *offsets = positions
        for offset in offsets:
            if offset != last_offset + 1:
                groups += 1
            last_offset = offset

        # Boost to favor less groups
        normalized_groups = (offset_count - (groups - 1)) / offset_count
        score *= 1 + (normalized_groups * normalized_groups)
        return score

    def _match(
        self, query: str, candidate: str
    ) -> Iterable[tuple[float, Sequence[int]]]:
        letter_positions: list[list[int]] = []
        position = 0

        if not self.case_sensitive:
            candidate = candidate.lower()
            query = query.lower()

        score = self.score

        for offset, letter in enumerate(query):
            last_index = len(candidate) - offset
            positions: list[int] = []
            letter_positions.append(positions)
            index = position
            while (location := candidate.find(letter, index)) != -1:
                positions.append(location)
                index = location + 1
                if index >= last_index:
                    break
            if not positions:
                yield (0.0, ())
                return
            position = positions[0] + 1

        possible_offsets: list[list[int]] = []
        query_length = len(query)

        def get_offsets(offsets: list[int], positions_index: int) -> None:
            """Recursively match offsets.

            Args:
                offsets: A list of offsets.
                positions_index: Index of query letter.

            """
            for offset in letter_positions[positions_index]:
                if not offsets or offset > offsets[-1]:
                    new_offsets = [*offsets, offset]
                    if len(new_offsets) == query_length:
                        possible_offsets.append(new_offsets)
                    else:
                        get_offsets(new_offsets, positions_index + 1)

        get_offsets([], 0)

        for offsets in possible_offsets:
            yield score(candidate, offsets), offsets


# Wrapper class that adapts the Rust API to match the Python API
class _RustCacheAdapter:
    """Adapter to make Rust cache compatible with Python LRUCache interface."""
    
    def __init__(self, rust_fuzzy: _RustFuzzySearch) -> None:
        self._rust_fuzzy = rust_fuzzy
    
    def grow(self, size: int) -> None:
        """Grow cache (no-op for Rust version which has dynamic cache)."""
        # Rust version uses a HashMap which grows automatically
        pass
    
    def clear(self) -> None:
        """Clear the cache."""
        self._rust_fuzzy.clear_cache()
    
    def __len__(self) -> int:
        """Get cache size."""
        return self._rust_fuzzy.cache_size()


class _RustFuzzySearchAdapter:
    """Adapter to make Rust FuzzySearch compatible with Python API."""
    
    def __init__(self, case_sensitive: bool = False, *, cache_size: int = 1024 * 4, path_mode: bool = False) -> None:
        # Rust version doesn't support configurable cache_size, but accepts case_sensitive and path_mode
        self._inner = _RustFuzzySearch(case_sensitive=case_sensitive, path_mode=path_mode)
        self.cache = _RustCacheAdapter(self._inner)
    
    def match(self, query: str, candidate: str) -> tuple[float, Sequence[int]]:
        """Match against a query (adapts match_ to match)."""
        return self._inner.match_(query, candidate)


# Export the appropriate implementation
if _RUST_AVAILABLE:
    FuzzySearch = _RustFuzzySearchAdapter
else:
    FuzzySearch = _PythonFuzzySearch


__all__ = ["FuzzySearch"]
