import asyncio

from collections import Counter, defaultdict
from asyncio import Lock
from itertools import islice
from operator import itemgetter


class FuzzyIndex:

    def __init__(self) -> None:
        self._paths: list[str] = []
        self._normalized_paths: list[str] = []
        self._index: dict[str, set[int]] = {}
        self._weights_cache: dict[str, dict[int, float]] = {}
        self._path_counter_cache: dict[str, Counter[str]] = {}
        self._lock = Lock()

    async def update_paths(self, paths: list[str]) -> None:
        """Update the paths and rebuild the index.

        Args:
            paths: New paths.
        """
        async with self._lock:
            self._paths = paths
            self._normalized_paths = await asyncio.to_thread(
                self._normalize_paths, paths
            )
            self._index = await asyncio.to_thread(
                self._build_trigram_index, self._normalized_paths
            )

    @classmethod
    def _normalize_paths(cls, paths: list[str]) -> list[str]:
        """Normalize the paths for searching.

        Args:
            paths: List of paths as strings.

        """
        normalized_paths = list(map(str.casefold, paths))
        return normalized_paths

    @classmethod
    def _extract_trigrams(cls, text: str) -> set[str]:
        """Return the set of all 3-character substrings (trigrams) in text.

        Padding with spaces ensures the start and end of the string are
        represented, so short strings and prefixes still produce trigrams.

        Args:
            text: candidate text (path).

        Returns:
            A set of 3 character strings.
        """
        padded = f"  {text} "
        return {padded[index : index + 3] for index in range(len(padded) - 2)}

    @classmethod
    def _build_trigram_index(cls, paths: list[str]) -> dict[str, set[int]]:
        """Build an inverted index mapping each trigram to the indices of paths containing it."""
        index: dict[str, set[int]] = defaultdict(set)
        for path_index, path in enumerate(paths):
            for trigram in cls._extract_trigrams(path):
                index[trigram].add(path_index)
        return index

    def _find_candidates(
        self,
        query: str,
        min_trigram_overlap: float = 0.3,
    ) -> list[tuple[str, str]]:
        """Return the indices of paths that share enough trigrams with the query.


        Args:
            query: The query to apply to the candidates.
            min_trigram_overlap: The overlap threshold (default 30%) controls the trade-off between
                recall (not missing real matches) and how many candidates get passed
                on to the slower detailed scoring stage.

        """
        query = query.casefold()
        if len(query) <= 2:
            slash_query = f"/{query}"
            candidates = list(
                islice(
                    (
                        (path, normalized_path)
                        for path, normalized_path in zip(
                            self._paths, self._normalized_paths
                        )
                        if normalized_path.startswith(query)
                        or slash_query in normalized_path
                    ),
                    None,
                    100,
                )
            )
            if candidates:
                return candidates
            candidates = list(
                islice(
                    (
                        (path, normalized_path)
                        for path, normalized_path in zip(
                            self._paths, self._normalized_paths
                        )
                        if query in normalized_path or slash_query in normalized_path
                    ),
                    None,
                    100,
                )
            )
            return candidates

        if len(query) == 3:
            min_trigram_overlap /= 2

        index = self._index
        query_trigrams = self._extract_trigrams(query)
        matching_buckets = [
            index[trigram] for trigram in query_trigrams if trigram in index
        ]

        trigram_match_counts = Counter(
            sorted(path_index for bucket in matching_buckets for path_index in bucket)
        )
        minimum_shared_trigrams = len(query_trigrams) * min_trigram_overlap
        unique_candidates = dict.fromkeys(
            islice(
                (
                    (self._paths[path_index], self._normalized_paths[path_index])
                    for path_index, count in trigram_match_counts.items()
                    if count >= minimum_shared_trigrams
                ),
                None,
                10000,
            )
        )
        candidates = list(unique_candidates.keys())
        return candidates

    @classmethod
    def make_weights(cls, path: str) -> dict[int, float]:
        weights: dict[int, float] = dict.fromkeys(
            range(path.rfind("/") + 1, len(path)), 1.0
        )
        index = path.find("/", None, -1)
        while index != -1:
            weights[index + 1] = weights.setdefault(index + 1, 1.0) + 1
            index = path.find("/", index + 1, -1)
        return weights

    async def search(self, query: str) -> list[str]:

        normalized_query = query.casefold()
        query_counter = Counter(normalized_query)

        scores: list[tuple[float, str]] = []

        TOP_COUNT = 100

        async with self._lock:
            for path, normalized_path in self._find_candidates(normalized_query):
                if (
                    path_counter := self._path_counter_cache.get(normalized_path)
                ) is None:
                    path_counter = self._path_counter_cache[normalized_path] = Counter(
                        normalized_path
                    )
                if query_counter - path_counter:
                    # Not all query characters are matched in the path
                    continue

                if (weights := self._weights_cache.get(normalized_path)) is None:
                    weights = self._weights_cache[normalized_path] = self.make_weights(
                        normalized_path
                    )

                score = sum(
                    [
                        weights.get(normalized_query.rfind(character), 0.0)
                        for character in normalized_path
                    ]
                )
                scores.append((score, path))

            scores.sort(reverse=True)
            top_scores = scores[:TOP_COUNT]

            return list(map(itemgetter(1), top_scores))


if __name__ == "__main__":

    # from textual._profile import timer

    from time import perf_counter
    import contextlib
    from typing import Generator

    @contextlib.contextmanager
    def timer(
        subject: str = "time", threshold: float = 0
    ) -> Generator[None, None, None]:
        """print the elapsed time. (only used in debugging).

        Args:
            subject: Text shown in log.
            threshold: Time in second after which the log is written.

        """
        start = perf_counter()
        yield
        elapsed = perf_counter() - start
        if elapsed >= threshold:
            elapsed_ms = elapsed * 1000
            print(f"{subject} elapsed {elapsed_ms:.4f}ms")

    async def run():
        with open("paths.txt") as f:
            PATHS = [line.rstrip() for line in f.readlines()]
        print(len(PATHS))
        # PATHS = [
        #     "~/foo/",
        #     "~/foo/bar/",
        #     "~/foo/bar/baz",
        #     "~/worldhello/foo",
        #     "~/Hello/world",
        # ]
        fuzzy = FuzzyIndex()
        with timer("update"):
            await fuzzy.update_paths(PATHS)
        with timer("search"):
            scores = await fuzzy.search("LICE")
        import rich

        rich.print(scores)

    import asyncio

    asyncio.run(run())
