#!/usr/bin/env python
"""Benchmark Rust vs Python fuzzy search implementations."""

import sys
import time
import os
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

def benchmark(name, fuzzy_search, test_cases, iterations=1000):
    """Benchmark a fuzzy search implementation."""
    start = time.perf_counter()
    
    for _ in range(iterations):
        for query, candidate in test_cases:
            fuzzy_search.match_(query, candidate) if hasattr(fuzzy_search, 'match_') else fuzzy_search.match(query, candidate)
    
    elapsed = time.perf_counter() - start
    return elapsed

def main():
    print("Fuzzy Search Performance Benchmark")
    print("=" * 60)
    
    # Test cases representing typical usage
    test_cases = [
        ('foo', 'foobar'),
        ('cmd', 'CommandPalette'),
        ('test', 'this is a test string'),
        ('fbr', 'foobar'),
        ('py', 'Python'),
        ('rust', 'RustImplementation'),
        ('search', 'FuzzySearchAlgorithm'),
        ('abc', 'alphabet soup with abc in it'),
    ]
    
    iterations = 1000
    
    print(f"\nRunning {iterations} iterations with {len(test_cases)} test cases each...")
    print(f"Total operations: {iterations * len(test_cases):,}\n")
    
    # Benchmark Python version
    print("Testing Python implementation...")
    py_fuzzy = _PythonFuzzySearch(case_sensitive=False)
    py_time = benchmark("Python", py_fuzzy, test_cases, iterations)
    
    # Benchmark Rust version  
    print("Testing Rust implementation...")
    rust_fuzzy = RustFuzzySearch(case_sensitive=False)
    rust_time = benchmark("Rust", rust_fuzzy, test_cases, iterations)
    
    # Results
    print("\n" + "=" * 60)
    print("Results:")
    print("-" * 60)
    print(f"Python:  {py_time:.3f}s  ({iterations * len(test_cases) / py_time:.0f} ops/sec)")
    print(f"Rust:    {rust_time:.3f}s  ({iterations * len(test_cases) / rust_time:.0f} ops/sec)")
    print("-" * 60)
    
    speedup = py_time / rust_time
    print(f"\n🚀 Rust is {speedup:.2f}x faster than Python!")
    
    # With caching (second run)
    print("\n" + "=" * 60)
    print("With caching (second run):")
    print("-" * 60)
    
    py_time_cached = benchmark("Python (cached)", py_fuzzy, test_cases, iterations)
    rust_time_cached = benchmark("Rust (cached)", rust_fuzzy, test_cases, iterations)
    
    print(f"Python:  {py_time_cached:.3f}s  ({iterations * len(test_cases) / py_time_cached:.0f} ops/sec)")
    print(f"Rust:    {rust_time_cached:.3f}s  ({iterations * len(test_cases) / rust_time_cached:.0f} ops/sec)")
    print("-" * 60)
    
    speedup_cached = py_time_cached / rust_time_cached
    print(f"\n🚀 With caching, Rust is {speedup_cached:.2f}x faster than Python!")

if __name__ == '__main__':
    main()
