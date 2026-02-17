# Rust Fuzzy Search

A high-performance Rust implementation of the fuzzy search algorithm for the Toad project, providing a drop-in replacement for the Python `toad.fuzzy` module.

## Features

- **Fast**: Implemented in Rust with optimizations enabled
- **Compatible**: Provides the same API and produces identical results as the Python implementation
- **Cached**: Includes built-in LRU caching for repeated queries

## Building

The Rust extension is built using [maturin](https://github.com/PyO3/maturin):

```bash
cd rust-fuzzy
maturin develop --release
```

Or use the Makefile from the project root:

```bash
make build-rust
```

## Usage

The Rust implementation provides a `FuzzySearch` class that can be used identically to the Python version:

```python
from toad._rust_fuzzy import FuzzySearch

# Create a fuzzy search instance
fuzzy = FuzzySearch(case_sensitive=False)

# Match a query against a candidate string
score, positions = fuzzy.match_('foo', 'foobar')
print(f"Score: {score}, Positions: {positions}")
# Output: Score: 8.0, Positions: [0, 1, 2]

# Cache management
print(f"Cache size: {fuzzy.cache_size()}")
fuzzy.clear_cache()
```

## API

### `FuzzySearch(case_sensitive=False)`

Create a new fuzzy search instance.

**Parameters:**
- `case_sensitive` (bool, optional): Whether matches should be case-sensitive. Defaults to `False`.

### `match_(query, candidate) -> (float, list[int])`

Match a query string against a candidate string.

**Parameters:**
- `query` (str): The search query
- `candidate` (str): The string to search in

**Returns:**
- A tuple of `(score, positions)` where:
  - `score` (float): The match score (higher is better, 0.0 for no match)
  - `positions` (list[int]): Character positions of the match in the candidate string

### `clear_cache()`

Clear the internal match cache.

### `cache_size() -> int`

Get the current number of entries in the cache.

## Performance

The Rust implementation provides significant performance improvements over the pure Python version, especially for:
- Large candidate strings
- Repeated queries (with caching)
- High-frequency fuzzy matching operations

## Development

### Testing

Run the comparison test to verify the Rust implementation matches the Python version:

```bash
python test_rust_fuzzy.py
```

### Debug Build

For development, you can build a debug version:

```bash
make build-rust-debug
```

## Implementation Details

The fuzzy search algorithm:
1. Finds all possible positions for each character in the query
2. Generates all valid character position combinations
3. Scores each combination based on:
   - Total number of matches
   - Matches at word boundaries (first letters)
   - Consecutive character groupings (fewer groups score higher)
4. Returns the highest-scoring match

The Rust implementation uses PyO3 for Python bindings and is compiled as a native extension module.
