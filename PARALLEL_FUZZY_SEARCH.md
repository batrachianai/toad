# Parallel Fuzzy Search Implementation

## Overview

The Rust fuzzy search implementation now supports parallel batch matching using the `rayon` library. This provides significant performance improvements when searching against large lists of candidates (1000+ paths).

## Features

### Parallel Batch Matching

The `match_batch` method processes multiple candidates in parallel across CPU cores:

```python
from toad.fuzzy import FuzzySearch

fuzzy = FuzzySearch(path_mode=True)
candidates = ["src/file1.py", "src/file2.py", ...]  # Large list of paths
results = fuzzy.match_batch("query", candidates)  # Parallel processing
```

### Automatic Parallelization Threshold

The implementation automatically decides when to use parallelism based on batch size:
- **< 1000 candidates**: Processes serially (thread overhead exceeds benefit)
- **≥ 1000 candidates**: Processes in parallel across available CPU cores

### Cache Integration

The batch matcher intelligently integrates with the cache:
1. Checks cache for all candidates first
2. Only processes uncached items in parallel
3. Updates cache with new results
4. Returns results in original order

## Performance Benchmarks

### Uncached Queries (Cold Cache)

Results from `benchmark_parallel_uncached.py`:

| Batch Size | Sequential | Parallel | Speedup |
|------------|-----------|----------|---------|
| 10 paths   | 0.01 ms   | 0.02 ms  | 0.94x   |
| 50 paths   | 0.07 ms   | 0.20 ms  | 0.35x   |
| 100 paths  | 0.14 ms   | 0.26 ms  | 0.55x   |
| 500 paths  | 0.68 ms   | 0.79 ms  | 0.87x   |
| **1000 paths** | **1.31 ms** | **0.94 ms** | **1.40x** |
| **2000 paths** | **2.53 ms** | **1.49 ms** | **1.70x** |
| **5000 paths** | **6.37 ms** | **2.83 ms** | **2.25x** |

**Key Findings:**
- Parallel processing becomes beneficial at ~1000 paths
- Speedup increases with batch size, reaching 2.25x at 5000 paths
- Thread overhead dominates for small batches

## Integration

### Path Search Widget

The `PathSearch` widget automatically uses batch matching when available:

```python
# In src/toad/widgets/path_search.py
if hasattr(fuzzy_search, 'match_batch'):
    candidates = [path.plain for path in self.highlighted_paths]
    batch_results = fuzzy_search.match_batch(search, candidates)
else:
    # Fallback to sequential matching
    results = [fuzzy_search.match(search, path) for path in candidates]
```

This provides automatic parallel search across all file paths in the project without any changes to the UI code.

## Technical Implementation

### Dependencies

Added to `rust-fuzzy/Cargo.toml`:
```toml
rayon = "1.10"
```

### Core Algorithm

```rust
fn match_batch(&mut self, query: &str, candidates: Vec<String>) -> Vec<(f64, Vec<usize>)> {
    const PARALLEL_THRESHOLD: usize = 1000;
    
    if candidates.len() < PARALLEL_THRESHOLD {
        // Serial processing for small batches
        candidates.iter()
            .map(|candidate| self.match_(query, candidate))
            .collect()
    } else {
        // Parallel processing for large batches
        // 1. Check cache for all candidates
        // 2. Process uncached items in parallel using rayon
        // 3. Update cache with results
        // 4. Return in original order
    }
}
```

### Thread Pool

Rayon automatically manages a global thread pool sized to the number of CPU cores. No manual thread management is required.

## Usage Examples

### Basic Usage

```python
from toad.fuzzy import FuzzySearch

# Create fuzzy search instance
fuzzy = FuzzySearch(case_sensitive=False, path_mode=True)

# Single match (existing API)
score, positions = fuzzy.match("test", "src/test_file.py")

# Batch match (new API, automatically parallel for large batches)
paths = ["src/file1.py", "src/file2.py", ...]  # 2000 paths
results = fuzzy.match_batch("test", paths)  # 1.7x faster than sequential
```

### Fallback Support

The Python implementation does not have `match_batch`, so code should check for availability:

```python
if hasattr(fuzzy_search, 'match_batch'):
    results = fuzzy_search.match_batch(query, candidates)
else:
    results = [fuzzy_search.match(query, c) for c in candidates]
```

## When to Use Batch Matching

### Use `match_batch` when:
- Searching against 1000+ candidates
- Processing the same query against multiple paths
- Using the Rust implementation (Toad's default)

### Use `match` when:
- Single candidate matching
- Small batches (< 1000 items)
- Need streaming/incremental results
- Using the Python fallback implementation

## Future Optimizations

Potential improvements for even better performance:

1. **Adaptive Threshold**: Dynamically adjust parallel threshold based on query complexity
2. **Work Stealing**: Better load balancing for uneven candidate lengths
3. **SIMD Optimizations**: Use SIMD instructions for character matching
4. **Lock-Free Cache**: Replace HashMap with concurrent data structure
5. **Batch Cache Lookups**: Optimize cache checking for large batches

## Testing

Run the benchmarks to verify performance:

```bash
# Compare sequential vs parallel with various batch sizes
uv run python benchmark_parallel_uncached.py

# Test correctness
uv run python test_rust_fuzzy.py
uv run python test_path_mode.py
```

## Conclusion

The parallel batch matching implementation provides significant speedups (1.4-2.25x) for large-scale fuzzy searching, with intelligent fallback to serial processing for small batches to avoid thread overhead. The feature integrates seamlessly with existing code through the optional `match_batch` method.
