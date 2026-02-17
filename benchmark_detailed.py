#!/usr/bin/env python
"""Detailed benchmark comparing Rust vs Python fuzzy search implementations."""

import sys
import time
from pathlib import Path

# Add paths
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / 'src'))

# Import both implementations
from toad.fuzzy import _PythonFuzzySearch
try:
    from toad._rust_fuzzy import FuzzySearch as RustFuzzySearch
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("⚠️  Rust implementation not available. Run 'make build-rust' first.")
    sys.exit(1)


def format_time(seconds):
    """Format time in appropriate units."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.1f}μs"
    elif seconds < 1:
        return f"{seconds * 1_000:.2f}ms"
    else:
        return f"{seconds:.3f}s"


def benchmark_scenario(name, fuzzy_python, fuzzy_rust, test_cases, iterations):
    """Benchmark a specific scenario."""
    print(f"\n{'='*70}")
    print(f"Scenario: {name}")
    print(f"{'='*70}")
    print(f"Test cases: {len(test_cases)}")
    print(f"Iterations: {iterations:,}")
    print(f"Total operations: {len(test_cases) * iterations:,}\n")
    
    # Python benchmark
    start = time.perf_counter()
    for _ in range(iterations):
        for query, candidate in test_cases:
            fuzzy_python.match(query, candidate)
    python_time = time.perf_counter() - start
    
    # Rust benchmark
    start = time.perf_counter()
    for _ in range(iterations):
        for query, candidate in test_cases:
            fuzzy_rust.match_(query, candidate)
    rust_time = time.perf_counter() - start
    
    # Results
    ops_count = len(test_cases) * iterations
    python_ops_per_sec = ops_count / python_time
    rust_ops_per_sec = ops_count / rust_time
    speedup = python_time / rust_time
    time_saved = (python_time - rust_time) * 1000  # in ms
    
    print(f"Results:")
    print(f"  Python: {format_time(python_time):>10}  ({python_ops_per_sec:>12,.0f} ops/sec)")
    print(f"  Rust:   {format_time(rust_time):>10}  ({rust_ops_per_sec:>12,.0f} ops/sec)")
    print(f"\n  Speedup: {speedup:.2f}x faster")
    print(f"  Time saved: {time_saved:.2f}ms per {iterations:,} iterations")
    
    # Per-operation time
    python_per_op = (python_time / ops_count) * 1_000_000  # microseconds
    rust_per_op = (rust_time / ops_count) * 1_000_000
    print(f"\n  Avg per operation:")
    print(f"    Python: {python_per_op:.2f}μs")
    print(f"    Rust:   {rust_per_op:.2f}μs")
    print(f"    Saved:  {python_per_op - rust_per_op:.2f}μs per operation")
    
    return {
        'python_time': python_time,
        'rust_time': rust_time,
        'speedup': speedup,
        'python_ops_per_sec': python_ops_per_sec,
        'rust_ops_per_sec': rust_ops_per_sec
    }


def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE FUZZY SEARCH PERFORMANCE BENCHMARK")
    print("="*70)
    
    # Create fresh instances for each test
    results = []
    
    # Scenario 1: Short strings (typical command palette)
    print("\n\n" + "▶"*70)
    print("TEST 1: Short strings (command palette simulation)")
    print("▶"*70)
    
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    
    short_strings = [
        ('cmd', 'command'),
        ('foo', 'foobar'),
        ('py', 'python'),
        ('rs', 'rust'),
        ('tst', 'test'),
    ]
    
    results.append(('Short strings', benchmark_scenario(
        "Short strings (5-10 chars)",
        py_fuzzy, rust_fuzzy,
        short_strings,
        10000
    )))
    
    # Scenario 2: Medium strings (typical file paths)
    print("\n\n" + "▶"*70)
    print("TEST 2: Medium strings (file path simulation)")
    print("▶"*70)
    
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    
    medium_strings = [
        ('fuzzy', 'src/toad/fuzzy_search.py'),
        ('test', 'tests/test_fuzzy_matching.py'),
        ('rust', 'rust-fuzzy/src/lib.rs'),
        ('config', 'config/settings.toml'),
        ('main', 'src/main_application.py'),
    ]
    
    results.append(('Medium strings', benchmark_scenario(
        "Medium strings (20-30 chars)",
        py_fuzzy, rust_fuzzy,
        medium_strings,
        5000
    )))
    
    # Scenario 3: Long strings (documentation/text search)
    print("\n\n" + "▶"*70)
    print("TEST 3: Long strings (text search simulation)")
    print("▶"*70)
    
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    
    long_strings = [
        ('search', 'This is a very long string that contains the word search somewhere in the middle of the text'),
        ('python', 'The Python programming language is a high-level, interpreted language with dynamic semantics'),
        ('rust', 'Rust is a systems programming language that runs blazingly fast and prevents segfaults'),
        ('fuzzy', 'Fuzzy matching algorithms are used to find approximate string matches in text processing'),
        ('performance', 'Performance optimization is crucial for interactive applications and user experience'),
    ]
    
    results.append(('Long strings', benchmark_scenario(
        "Long strings (70-100 chars)",
        py_fuzzy, rust_fuzzy,
        long_strings,
        2000
    )))
    
    # Scenario 4: Non-matching (worst case)
    print("\n\n" + "▶"*70)
    print("TEST 4: Non-matching queries (worst case)")
    print("▶"*70)
    
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    
    non_matching = [
        ('xyz', 'abcdefghijklmnop'),
        ('qrs', 'abcdefghijklmnop'),
        ('tuv', 'abcdefghijklmnop'),
        ('www', 'abcdefghijklmnop'),
        ('zzz', 'abcdefghijklmnop'),
    ]
    
    results.append(('Non-matching', benchmark_scenario(
        "Non-matching queries",
        py_fuzzy, rust_fuzzy,
        non_matching,
        10000
    )))
    
    # Scenario 5: With caching (realistic usage)
    print("\n\n" + "▶"*70)
    print("TEST 5: With caching (repeated queries)")
    print("▶"*70)
    
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    
    # Prime the cache
    for query, candidate in short_strings:
        py_fuzzy.match(query, candidate)
        rust_fuzzy.match_(query, candidate)
    
    results.append(('Cached', benchmark_scenario(
        "Cached queries (repeated)",
        py_fuzzy, rust_fuzzy,
        short_strings,
        50000
    )))
    
    # Summary
    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print("\nSpeedup by scenario:")
    print("-" * 70)
    for name, result in results:
        print(f"  {name:20s}: {result['speedup']:5.2f}x faster")
    
    avg_speedup = sum(r['speedup'] for _, r in results) / len(results)
    print("-" * 70)
    print(f"  {'Average':20s}: {avg_speedup:5.2f}x faster")
    print()
    
    # Overall statistics
    total_python_time = sum(r['python_time'] for _, r in results)
    total_rust_time = sum(r['rust_time'] for _, r in results)
    overall_speedup = total_python_time / total_rust_time
    time_saved_ms = (total_python_time - total_rust_time) * 1000
    
    print(f"\nOverall Performance:")
    print(f"  Total Python time: {format_time(total_python_time)}")
    print(f"  Total Rust time:   {format_time(total_rust_time)}")
    print(f"  Overall speedup:   {overall_speedup:.2f}x")
    print(f"  Total time saved:  {time_saved_ms:.1f}ms")
    
    print("\n" + "="*70)
    print(f"🚀 Rust implementation is {overall_speedup:.2f}x faster overall!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
