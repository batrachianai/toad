#!/usr/bin/env python3
"""Benchmark Rust vs Python directory scanning."""

import asyncio
import time
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from toad.directory import scan, _RUST_AVAILABLE
from toad.path_filter import PathFilter
import toad.directory as directory_module

async def benchmark_python(root: Path, path_filter: PathFilter | None, iterations: int = 3):
    """Benchmark Python implementation."""
    # Force Python implementation
    original_rust = directory_module._RUST_AVAILABLE
    directory_module._RUST_AVAILABLE = False
    
    times = []
    results = None
    
    for i in range(iterations):
        start = time.perf_counter()
        paths = await scan(root, path_filter=path_filter, max_duration=10.0)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        if i == 0:
            results = paths
    
    # Restore Rust availability
    directory_module._RUST_AVAILABLE = original_rust
    
    # Return median time and result count
    return sorted(times)[len(times)//2], len(results)

async def benchmark_rust(root: Path, path_filter: PathFilter | None, iterations: int = 3):
    """Benchmark Rust implementation."""
    if not _RUST_AVAILABLE:
        return None, 0
    
    times = []
    results = None
    
    for i in range(iterations):
        start = time.perf_counter()
        paths = await scan(root, path_filter=path_filter, max_duration=10.0)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        if i == 0:
            results = paths
    
    # Return median time and result count
    return sorted(times)[len(times)//2], len(results)

async def main():
    print("=" * 80)
    print("RUST vs PYTHON DIRECTORY SCANNER COMPARISON")
    print("=" * 80)
    print()
    
    scan_path = Path("/Users/willmcgugan/projects/external/TypeScript")
    
    if not scan_path.exists():
        print(f"Error: Path does not exist: {scan_path}")
        return
    
    print(f"Scanning: {scan_path}")
    print(f"Rust available: {_RUST_AVAILABLE}")
    print()
    
    # Test scenarios
    scenarios = [
        ("No filter", None),
        ("With gitignore filter", PathFilter.from_git_root(scan_path)),
    ]
    
    for scenario_name, path_filter in scenarios:
        print("-" * 80)
        print(f"Scenario: {scenario_name}")
        print("-" * 80)
        
        # Python benchmark
        print("\nPython Implementation:")
        print("  Running 3 iterations...")
        py_time, py_count = await benchmark_python(scan_path, path_filter, iterations=3)
        print(f"  Time:  {py_time:.4f}s (median of 3)")
        print(f"  Files: {py_count}")
        
        # Rust benchmark
        if _RUST_AVAILABLE:
            print("\nRust Implementation:")
            print("  Running 3 iterations...")
            rust_time, rust_count = await benchmark_rust(scan_path, path_filter, iterations=3)
            print(f"  Time:  {rust_time:.4f}s (median of 3)")
            print(f"  Files: {rust_count}")
            
            # Comparison
            speedup = py_time / rust_time if rust_time > 0 else 0
            print(f"\nSpeedup: {speedup:.2f}x faster")
            
            if abs(py_count - rust_count) > 0:
                print(f"⚠ Warning: File counts differ (Python: {py_count}, Rust: {rust_count})")
        else:
            print("\n⚠ Rust implementation not available")
        
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("The Rust implementation provides significant speedups through:")
    print("  - Multi-threaded parallel scanning")
    print("  - Work-stealing queue for load balancing")
    print("  - Lock-free synchronization")
    print("  - Efficient directory traversal")
    print()
    print("Note: With filters, both implementations scan all directories but")
    print("      Rust is still faster due to parallelism. Future enhancement:")
    print("      pass filter to Rust to skip filtered dirs entirely.")

if __name__ == "__main__":
    asyncio.run(main())
