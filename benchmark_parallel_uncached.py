#!/usr/bin/env python3
"""Benchmark parallel batch matching performance with uncached queries."""

import time
from toad._rust_fuzzy import FuzzySearch as RustFuzzySearch

def generate_paths(count: int) -> list[str]:
    """Generate a realistic list of file paths."""
    paths = []
    for i in range(count):
        if i % 10 == 0:
            paths.append(f"src/components/Button{i}.tsx")
        elif i % 10 == 1:
            paths.append(f"src/utils/helper{i}.ts")
        elif i % 10 == 2:
            paths.append(f"tests/unit/test_{i}.py")
        elif i % 10 == 3:
            paths.append(f"docs/api/reference{i}.md")
        elif i % 10 == 4:
            paths.append(f"config/settings_{i}.json")
        elif i % 10 == 5:
            paths.append(f"lib/vendor/module{i}.js")
        elif i % 10 == 6:
            paths.append(f"build/output/artifact{i}.o")
        elif i % 10 == 7:
            paths.append(f"assets/images/icon{i}.png")
        elif i % 10 == 8:
            paths.append(f"scripts/deploy/task{i}.sh")
        else:
            paths.append(f"data/cache/file{i}.dat")
    return paths

def benchmark_sequential_uncached(query: str, paths: list[str]) -> float:
    """Benchmark sequential matching without cache."""
    fuzzy_search = RustFuzzySearch(case_sensitive=False, path_mode=True)
    start = time.perf_counter()
    results = [fuzzy_search.match_(query, path) for path in paths]
    elapsed = time.perf_counter() - start
    return elapsed

def benchmark_batch_uncached(query: str, paths: list[str]) -> float:
    """Benchmark parallel batch matching without cache."""
    fuzzy_search = RustFuzzySearch(case_sensitive=False, path_mode=True)
    start = time.perf_counter()
    results = fuzzy_search.match_batch(query, paths)
    elapsed = time.perf_counter() - start
    return elapsed

def main():
    print("=" * 70)
    print("PARALLEL BATCH MATCHING BENCHMARK (UNCACHED)")
    print("=" * 70)
    print()
    
    # Test with different batch sizes
    batch_sizes = [10, 50, 100, 500, 1000, 2000, 5000]
    query = "test"
    
    for size in batch_sizes:
        print(f"Batch size: {size} paths")
        print("-" * 70)
        
        paths = generate_paths(size)
        
        # Run multiple times and take the best result to minimize variance
        seq_times = []
        batch_times = []
        
        for _ in range(5):
            seq_times.append(benchmark_sequential_uncached(query, paths))
            batch_times.append(benchmark_batch_uncached(query, paths))
        
        # Use median to avoid outliers
        seq_time = sorted(seq_times)[len(seq_times)//2]
        batch_time = sorted(batch_times)[len(batch_times)//2]
        
        speedup = seq_time / batch_time if batch_time > 0 else 0
        
        print(f"  Sequential: {seq_time*1000:.2f} ms")
        print(f"  Batch:      {batch_time*1000:.2f} ms")
        print(f"  Speedup:    {speedup:.2f}x")
        
        if speedup > 1.0:
            print(f"  ✓ Batch is {speedup:.2f}x faster")
        else:
            print(f"  ✗ Sequential is {1/speedup:.2f}x faster")
        print()
    
    print("=" * 70)
    print("Note: The parallel threshold is 50 paths")
    print("      Speedup should increase with batch size")
    print("=" * 70)

if __name__ == "__main__":
    main()
