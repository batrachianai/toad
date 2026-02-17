#!/usr/bin/env python3
"""Comprehensive benchmark showing all optimizations."""

import time
import sys
sys.path.insert(0, 'src')

# Force Python implementation for comparison
import toad.fuzzy as fuzzy_module
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

def benchmark(name: str, fn, iterations: int = 5) -> float:
    """Run benchmark and return median time."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return sorted(times)[len(times)//2]

def main():
    print("=" * 80)
    print("COMPLETE FUZZY SEARCH OPTIMIZATION BENCHMARK")
    print("=" * 80)
    print()
    print("Scenario: Search for 'test' in 5000 file paths, return top 20 results")
    print("This simulates the real-world path search widget use case.")
    print()
    
    query = "test"
    num_paths = 5000
    k = 20
    paths = generate_paths(num_paths)
    
    print(f"Testing with {num_paths} paths, finding top {k} matches...")
    print("-" * 80)
    
    # 1. Python baseline
    print("\n1. Python Implementation (Baseline)")
    print("   Single-threaded Python with LRU cache")
    
    def python_search():
        fuzzy = fuzzy_module._PythonFuzzySearch(case_sensitive=False, path_mode=True)
        results = []
        for path in paths:
            score, positions = fuzzy.match(query, path)
            if score > 0:
                results.append((score, positions, path))
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:k]
    
    python_time = benchmark("Python", python_search)
    print(f"   Time: {python_time*1000:.2f} ms")
    print(f"   Speedup: 1.0x (baseline)")
    
    # 2. Rust sequential
    print("\n2. Rust Sequential")
    print("   Single-threaded Rust with early rejection optimization")
    
    def rust_sequential():
        fuzzy = RustFuzzySearch(case_sensitive=False, path_mode=True)
        results = []
        for path in paths:
            score, positions = fuzzy.match_(query, path)
            if score > 0:
                results.append((score, positions, path))
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:k]
    
    rust_seq_time = benchmark("Rust Sequential", rust_sequential)
    speedup = python_time / rust_seq_time
    print(f"   Time: {rust_seq_time*1000:.2f} ms")
    print(f"   Speedup: {speedup:.2f}x vs Python")
    
    # 3. Rust batch (parallel)
    print("\n3. Rust Batch (Parallel)")
    print("   Multi-threaded Rust using rayon for parallelism")
    
    def rust_batch():
        fuzzy = RustFuzzySearch(case_sensitive=False, path_mode=True)
        results = fuzzy.match_batch(query, paths)
        scored = [(score, positions, path) for (score, positions), path in zip(results, paths) if score > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]
    
    rust_batch_time = benchmark("Rust Batch", rust_batch)
    speedup = python_time / rust_batch_time
    improvement = rust_seq_time / rust_batch_time
    print(f"   Time: {rust_batch_time*1000:.2f} ms")
    print(f"   Speedup: {speedup:.2f}x vs Python, {improvement:.2f}x vs Rust Sequential")
    
    # 4. Rust top-K (parallel + heap optimization)
    print("\n4. Rust Top-K (Parallel + Heap Optimization)")
    print("   Multi-threaded with min-heap for tracking top K results")
    
    def rust_topk():
        fuzzy = RustFuzzySearch(case_sensitive=False, path_mode=True)
        results = fuzzy.match_batch_top_k(query, paths, k)
        return results
    
    rust_topk_time = benchmark("Rust Top-K", rust_topk)
    speedup_python = python_time / rust_topk_time
    speedup_rust_seq = rust_seq_time / rust_topk_time
    speedup_rust_batch = rust_batch_time / rust_topk_time
    print(f"   Time: {rust_topk_time*1000:.2f} ms")
    print(f"   Speedup: {speedup_python:.2f}x vs Python")
    print(f"            {speedup_rust_seq:.2f}x vs Rust Sequential")
    print(f"            {speedup_rust_batch:.2f}x vs Rust Batch")
    
    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print()
    print(f"{'Method':<30} {'Time (ms)':<12} {'vs Python':<12} {'vs Baseline'}")
    print("-" * 80)
    print(f"{'Python (baseline)':<30} {python_time*1000:>8.2f} ms  {1.0:>8.2f}x      -")
    print(f"{'Rust Sequential':<30} {rust_seq_time*1000:>8.2f} ms  {python_time/rust_seq_time:>8.2f}x   {1.0:>6.2f}x")
    print(f"{'Rust Batch (Parallel)':<30} {rust_batch_time*1000:>8.2f} ms  {python_time/rust_batch_time:>8.2f}x   {rust_seq_time/rust_batch_time:>6.2f}x")
    print(f"{'Rust Top-K (Best)':<30} {rust_topk_time*1000:>8.2f} ms  {speedup_python:>8.2f}x   {speedup_rust_seq:>6.2f}x")
    print()
    
    # Calculate total speedup
    print("=" * 80)
    print(f"TOTAL OPTIMIZATION: {speedup_python:.2f}x faster than Python")
    print(f"                    {speedup_rust_seq:.2f}x faster than baseline Rust")
    print("=" * 80)
    print()
    print("Key Optimizations Applied:")
    print("  1. Early rejection (HashSet character check)")
    print("  2. Parallel processing (Rayon across CPU cores)")
    print("  3. Top-K heap (avoid sorting all results)")
    print("  4. Efficient caching (cache-aware parallel batching)")
    print()
    print("This performance makes fuzzy search feel instant even in large codebases!")
    print("=" * 80)

if __name__ == "__main__":
    main()
