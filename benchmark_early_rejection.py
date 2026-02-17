#!/usr/bin/env python
"""Benchmark specifically for early rejection optimization."""

import sys
import time
from pathlib import Path

# Add paths
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / 'src'))

from toad.fuzzy import _PythonFuzzySearch
try:
    from toad._rust_fuzzy import FuzzySearch as RustFuzzySearch
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("⚠️  Rust implementation not available. Run 'make build-rust' first.")
    sys.exit(1)


def benchmark(name, test_cases, iterations):
    """Benchmark both implementations."""
    print(f"\n{'='*70}")
    print(f"Test: {name}")
    print(f"{'='*70}")
    print(f"Test cases: {len(test_cases)}")
    print(f"Iterations: {iterations:,}")
    print(f"Total operations: {len(test_cases) * iterations:,}\n")
    
    # Python
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    start = time.perf_counter()
    for _ in range(iterations):
        for query, candidate in test_cases:
            py_fuzzy.match(query, candidate)
    py_time = time.perf_counter() - start
    
    # Rust
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    start = time.perf_counter()
    for _ in range(iterations):
        for query, candidate in test_cases:
            rust_fuzzy.match_(query, candidate)
    rust_time = time.perf_counter() - start
    
    # Results
    ops = len(test_cases) * iterations
    py_per_op = (py_time / ops) * 1_000_000  # microseconds
    rust_per_op = (rust_time / ops) * 1_000_000
    speedup = py_time / rust_time
    
    print(f"Results:")
    print(f"  Python: {py_time*1000:.2f}ms  ({py_per_op:.3f}μs per op)")
    print(f"  Rust:   {rust_time*1000:.2f}ms  ({rust_per_op:.3f}μs per op)")
    print(f"\n  Speedup: {speedup:.2f}x")
    print(f"  Saved: {(py_per_op - rust_per_op):.3f}μs per operation ({((py_per_op - rust_per_op)/py_per_op*100):.1f}%)")
    
    return speedup


def main():
    print("\n" + "="*70)
    print("EARLY REJECTION OPTIMIZATION BENCHMARK")
    print("="*70)
    print("\nThis benchmark focuses on scenarios where early rejection helps most.")
    
    results = []
    
    # Test 1: Complete non-matches (best case for early rejection)
    print("\n\n" + "▶"*70)
    print("TEST 1: Complete Non-Matches (all query chars missing)")
    print("▶"*70)
    
    complete_non_matches = [
        ('xyz', 'abcdefghijklmnop'),
        ('qrs', 'abcdefghijklmnop'),
        ('tuv', 'abcdefghijklmnop'),
        ('123', 'abcdefghijklmnop'),
        ('!@#', 'abcdefghijklmnop'),
    ]
    
    results.append(('Complete non-matches', benchmark(
        'All query characters missing',
        complete_non_matches,
        20000
    )))
    
    # Test 2: Partial non-matches (some chars present)
    print("\n\n" + "▶"*70)
    print("TEST 2: Partial Non-Matches (some chars missing)")
    print("▶"*70)
    
    partial_non_matches = [
        ('axz', 'abcdefghijklmnop'),  # 'a' present, 'x' and 'z' missing
        ('bxy', 'abcdefghijklmnop'),
        ('cxz', 'abcdefghijklmnop'),
        ('dxy', 'abcdefghijklmnop'),
        ('exz', 'abcdefghijklmnop'),
    ]
    
    results.append(('Partial non-matches', benchmark(
        'Some query characters missing',
        partial_non_matches,
        20000
    )))
    
    # Test 3: All chars present but no valid match (early rejection doesn't help)
    print("\n\n" + "▶"*70)
    print("TEST 3: All Chars Present (early rejection skipped)")
    print("▶"*70)
    
    chars_present_no_match = [
        ('zyx', 'abcdefghijklmnopqrstuvwxyz'),  # All present but wrong order
        ('dcba', 'abcdefgh'),
        ('hgfe', 'abcdefgh'),
        ('ponm', 'abcdefghijklmnop'),
        ('mlkj', 'abcdefghijklmnop'),
    ]
    
    results.append(('Chars present, no match', benchmark(
        'All characters present but no valid fuzzy match',
        chars_present_no_match,
        20000
    )))
    
    # Test 4: Actual matches (control group)
    print("\n\n" + "▶"*70)
    print("TEST 4: Successful Matches (control)")
    print("▶"*70)
    
    matches = [
        ('abc', 'abcdefgh'),
        ('def', 'abcdefgh'),
        ('cmd', 'command'),
        ('foo', 'foobar'),
        ('test', 'testing'),
    ]
    
    results.append(('Successful matches', benchmark(
        'Normal successful matches',
        matches,
        20000
    )))
    
    # Test 5: Long candidates with early rejection
    print("\n\n" + "▶"*70)
    print("TEST 5: Long Candidates (early rejection benefit)")
    print("▶"*70)
    
    long_non_matches = [
        ('xyz', 'The quick brown fox jumps over the lazy dog in the meadow'),
        ('123', 'The quick brown fox jumps over the lazy dog in the meadow'),
        ('qqq', 'The quick brown fox jumps over the lazy dog in the meadow'),
        ('zzz', 'The quick brown fox jumps over the lazy dog in the meadow'),
        ('www', 'The quick brown fox jumps over the lazy dog in the meadow'),
    ]
    
    results.append(('Long non-matches', benchmark(
        'Long candidates with missing chars',
        long_non_matches,
        10000
    )))
    
    # Summary
    print("\n\n" + "="*70)
    print("SUMMARY - Impact of Early Rejection")
    print("="*70)
    print("\nSpeedup by scenario:")
    print("-" * 70)
    for name, speedup in results:
        print(f"  {name:30s}: {speedup:5.2f}x")
    
    avg_speedup = sum(s for _, s in results) / len(results)
    print("-" * 70)
    print(f"  {'Average':30s}: {avg_speedup:5.2f}x")
    
    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    complete_speedup = results[0][1]
    partial_speedup = results[1][1]
    no_rejection_speedup = results[2][1]
    match_speedup = results[3][1]
    
    print(f"\nEarly rejection effectiveness:")
    print(f"  Complete non-matches:    {complete_speedup:.2f}x (best case)")
    print(f"  Partial non-matches:     {partial_speedup:.2f}x")
    print(f"  No rejection applies:    {no_rejection_speedup:.2f}x (baseline)")
    print(f"  Successful matches:      {match_speedup:.2f}x (control)")
    
    rejection_benefit = complete_speedup - no_rejection_speedup
    print(f"\n  Early rejection benefit: +{rejection_benefit:.2f}x speedup")
    print(f"  Improvement over baseline: {(rejection_benefit/no_rejection_speedup)*100:.1f}%")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
