#!/usr/bin/env python3
"""Benchmark parallel batch matching performance."""

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

def benchmark_sequential(fuzzy_search: RustFuzzySearch, query: str, paths: list[str], iterations: int = 10) -> float:
    """Benchmark sequential matching."""
    start = time.perf_counter()
    for _ in range(iterations):
        results = [fuzzy_search.match_(query, path) for path in paths]
    elapsed = time.perf_counter() - start
    return elapsed / iterations

def benchmark_batch(fuzzy_search: RustFuzzySearch, query: str, paths: list[str], iterations: int = 10) -> float:
    """Benchmark parallel batch matching."""
    start = time.perf_counter()
    for _ in range(iterations):
        results = fuzzy_search.match_batch(query, paths)
    elapsed = time.perf_counter() - start
    return elapsed / iterations

def main():
    print("=" * 70)
    print("PARALLEL BATCH MATCHING BENCHMARK")
    print("=" * 70)
    print()
    
    # Test with different batch sizes
    batch_sizes = [10, 50, 100, 500, 1000, 2000]
    query = "test"
    
    for size in batch_sizes:
        print(f"Batch size: {size} paths")
        print("-" * 70)
        
        paths = generate_paths(size)
        
        # Create fresh instances for each test
        fuzzy_sequential = RustFuzzySearch(case_sensitive=False, path_mode=True)
        fuzzy_batch = RustFuzzySearch(case_sensitive=False, path_mode=True)
        
        # Warm up
        for path in paths[:10]:
            fuzzy_sequential.match_(query, path)
        fuzzy_batch.match_batch(query, paths[:10])
        
        # Benchmark
        iterations = max(3, 100 // (size // 10 + 1))  # Fewer iterations for larger batches
        
        seq_time = benchmark_sequential(fuzzy_sequential, query, paths, iterations)
        batch_time = benchmark_batch(fuzzy_batch, query, paths, iterations)
        
        speedup = seq_time / batch_time if batch_time > 0 else 0
        
        print(f"  Sequential: {seq_time*1000:.2f} ms")
        print(f"  Batch:      {batch_time*1000:.2f} ms")
        print(f"  Speedup:    {speedup:.2f}x")
        print()
    
    print("=" * 70)
    print("Note: Speedup > 1.0 indicates batch matching is faster")
    print("      The parallel threshold is 50 paths, so expect speedup")
    print("      to be minimal below that threshold.")
    print("=" * 70)

if __name__ == "__main__":
    main()
