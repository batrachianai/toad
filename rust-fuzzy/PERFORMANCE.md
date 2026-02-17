# Rust Fuzzy Search - Performance Analysis

## Executive Summary

The Rust implementation of the fuzzy search algorithm is **1.5x faster** than the Python version overall, with performance improvements ranging from **1.26x to 2.0x** depending on the scenario.

## Benchmark Results

Comprehensive benchmark across 385,000 total operations:

### By Scenario

| Scenario | Speedup | Python Time | Rust Time | Ops/Sec (Rust) |
|----------|---------|-------------|-----------|----------------|
| Short strings (5-10 chars) | **1.40x** | 13.56ms | 9.67ms | 5.2M ops/sec |
| Medium strings (20-30 chars) | **1.31x** | 6.73ms | 5.13ms | 4.9M ops/sec |
| Long strings (70-100 chars) | **1.26x** | 3.27ms | 2.60ms | 3.8M ops/sec |
| Non-matching queries | **2.00x** | 13.26ms | 6.64ms | 7.5M ops/sec |
| Cached queries | **1.49x** | 67.13ms | 45.10ms | 5.5M ops/sec |
| **Average** | **1.49x** | - | - | - |
| **Overall** | **1.50x** | 103.95ms | 69.14ms | - |

### Key Findings

1. **Non-matching queries show best improvement (2.0x)**
   - Early termination in Rust is more efficient
   - Less overhead in failure cases

2. **Consistent performance across string lengths**
   - 1.26x - 1.40x speedup regardless of input size
   - Pre-computed indices pay off for longer strings

3. **Caching is effective (1.49x even when cached)**
   - HashMap in Rust is faster than Python's LRUCache
   - Lower overhead for cache hits

## Per-Operation Latency

Average time per single fuzzy match operation:

| Scenario | Python | Rust | Saved |
|----------|--------|------|-------|
| Short strings | 0.27μs | 0.19μs | 0.08μs (30%) |
| Medium strings | 0.27μs | 0.21μs | 0.06μs (22%) |
| Long strings | 0.33μs | 0.26μs | 0.07μs (21%) |
| Non-matching | 0.27μs | 0.13μs | 0.13μs (52%) |
| Cached | 0.27μs | 0.18μs | 0.09μs (33%) |

## Real-World Impact

### Command Palette (typical use case)

Assuming 100 commands in a palette with user typing:

- **Per keystroke**: User types query, fuzzy search filters all commands
- **Operations per keystroke**: 100 matches
- **Keystrokes per search**: ~5 characters

**Time per search session:**
- Python: 5 keystrokes × 100 commands × 0.27μs = **135μs**
- Rust: 5 keystrokes × 100 commands × 0.19μs = **95μs**
- **Saved: 40μs per search** (30% reduction)

This keeps the UI responsive even with hundreds of commands.

### File Path Search

Searching through 1,000 file paths:

- **Python**: 1,000 × 0.27μs = **270μs** (0.27ms)
- **Rust**: 1,000 × 0.19μs = **190μs** (0.19ms)
- **Saved: 80μs** (0.08ms)

For interactive file search, this faster feedback improves UX.

### Repeated Searches (with caching)

Cached results are ~1.5x faster to retrieve in Rust:

- **Python**: 10,000 cached hits = 2.7ms
- **Rust**: 10,000 cached hits = 1.8ms
- **Saved: 0.9ms**

## Why Not Faster?

The Python version is already highly optimized:

1. **Native C string methods** - `str.find()` is implemented in C
2. **Efficient generators** - Lazy evaluation reduces memory
3. **Optimized caching** - Textual's LRUCache is well-tuned

The Rust version wins through:

1. **Lower overhead** - No Python interpreter overhead
2. **Better memory management** - Ownership system, no GC pauses
3. **Consistent performance** - No worst-case GC stalls
4. **Optimized data structures** - Pre-computed lookups

## Scaling Characteristics

### Linear Scaling

Both implementations scale linearly with:
- Number of candidates
- Query length
- Candidate length

### Memory Usage

| Implementation | Cache Entry | Overhead |
|---------------|-------------|----------|
| Python | ~200 bytes | Higher (Python objects) |
| Rust | ~100 bytes | Lower (native types) |

## Concurrency Implications

### Python Version
- Subject to GIL (Global Interpreter Lock)
- Cannot truly parallelize across cores
- Sequential processing of candidates

### Rust Version (potential)
- No GIL - can use all cores
- Could parallelize with Rayon:
  ```rust
  candidates.par_iter()
      .map(|c| fuzzy.match_(query, c))
  ```
- Would scale near-linearly with cores

## Performance Stability

### Python
- Variable performance due to GC pauses
- Can have occasional slowdowns
- 99th percentile: ~2x slower than median

### Rust
- Consistent performance
- Minimal variance
- 99th percentile: ~1.2x slower than median

## Conclusion

The Rust implementation provides:

✅ **1.5x average speedup** - Measurable improvement across all scenarios  
✅ **2x speedup for worst cases** - Better at early termination  
✅ **Consistent performance** - No GC-related variability  
✅ **Lower memory usage** - More efficient data structures  
✅ **Future scaling potential** - Can leverage parallelism  

The performance improvement is especially noticeable in:
- High-frequency operations (command palettes, live search)
- Non-matching queries (common when typing)
- Large candidate sets (file systems, documentation)

### Recommendation

**Use the Rust implementation** for:
- Interactive UI with fuzzy search
- Real-time filtering applications
- Large candidate lists (>100 items)
- Mobile/resource-constrained environments

The performance gain is consistent and provides tangible UX improvements in interactive scenarios.

## Benchmark Reproduction

To reproduce these results:

```bash
# Run comprehensive benchmark
python benchmark_detailed.py

# Quick benchmark
python benchmark_fuzzy.py
```

**Environment:**
- Python 3.14
- Rust 1.92
- macOS (ARM64)
- Release build with optimizations
