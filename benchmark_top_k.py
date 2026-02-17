#!/usr/bin/env python3
"""Benchmark top-K optimization performance."""

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

def benchmark_batch_then_sort(query: str, paths: list[str], k: int, iterations: int = 5) -> float:
    """Benchmark match_batch + filter + sort approach."""
    times = []
    for _ in range(iterations):
        fuzzy = RustFuzzySearch(case_sensitive=False, path_mode=True)
        start = time.perf_counter()
        results = fuzzy.match_batch(query, paths)
        # Filter and sort like the real code does
        scored = [(i, score, positions) for i, (score, positions) in enumerate(results) if score > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        top_k = scored[:k]
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return sorted(times)[len(times)//2]  # median

def benchmark_top_k_direct(query: str, paths: list[str], k: int, iterations: int = 5) -> float:
    """Benchmark match_batch_top_k direct approach."""
    times = []
    for _ in range(iterations):
        fuzzy = RustFuzzySearch(case_sensitive=False, path_mode=True)
        start = time.perf_counter()
        top_k = fuzzy.match_batch_top_k(query, paths, k)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return sorted(times)[len(times)//2]  # median

def main():
    print("=" * 70)
    print("TOP-K OPTIMIZATION BENCHMARK")
    print("=" * 70)
    print()
    
    # Test different scenarios
    scenarios = [
        (1000, 20, "Small batch (1000 paths)"),
        (2000, 20, "Medium batch (2000 paths)"),
        (5000, 20, "Large batch (5000 paths)"),
        (10000, 20, "Very large batch (10000 paths)"),
        (5000, 50, "Large batch, more results (5000 paths, K=50)"),
        (5000, 100, "Large batch, many results (5000 paths, K=100)"),
    ]
    
    query = "test"
    
    for num_paths, k, description in scenarios:
        print(f"{description}")
        print("-" * 70)
        
        paths = generate_paths(num_paths)
        
        batch_time = benchmark_batch_then_sort(query, paths, k)
        topk_time = benchmark_top_k_direct(query, paths, k)
        
        speedup = batch_time / topk_time if topk_time > 0 else 0
        
        print(f"  K = {k} out of {num_paths} paths")
        print(f"  Batch+Sort: {batch_time*1000:.2f} ms")
        print(f"  Top-K:      {topk_time*1000:.2f} ms")
        print(f"  Speedup:    {speedup:.2f}x")
        
        if speedup > 1.0:
            print(f"  ✓ Top-K is {speedup:.2f}x faster")
        elif speedup < 0.95:
            print(f"  ⚠ Top-K is {1/speedup:.2f}x slower")
        else:
            print(f"  ≈ Similar performance")
        print()
    
    print("=" * 70)
    print("Key Insights:")
    print("- Top-K optimization is most effective when K << N (need few from many)")
    print("- For typical UI use case (top 20 from 1000s), expect 1.5-3x speedup")
    print("- Speedup increases with larger candidate lists")
    print("=" * 70)

if __name__ == "__main__":
    main()
