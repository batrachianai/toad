"""Compare files found by Rust vs Python implementations."""
import asyncio
from pathlib import Path
from toad.directory import scan
from toad.path_filter import PathFilter
from toad._rust_fuzzy import scan_directory_parallel as rust_scan

async def main():
    scan_path = Path("/Users/willmcgugan/projects/external/TypeScript")
    path_filter = PathFilter.from_git_root(scan_path)
    
    # Python scan
    print("Running Python scan...")
    python_paths = await scan(scan_path, path_filter=path_filter, max_duration=None)
    python_set = set(str(p) for p in python_paths)
    print(f"Python found: {len(python_set)} files")
    
    # Rust scan (without post-filtering)
    print("Running Rust scan...")
    rust_paths_raw = rust_scan(str(scan_path), False, None)
    rust_set = set(rust_paths_raw)
    print(f"Rust found: {len(rust_set)} files")
    
    # Find differences
    only_python = python_set - rust_set
    only_rust = rust_set - python_set
    
    print(f"\nFiles only in Python ({len(only_python)}):")
    for p in sorted(only_python)[:10]:
        print(f"  {p}")
    if len(only_python) > 10:
        print(f"  ... and {len(only_python) - 10} more")
    
    print(f"\nFiles only in Rust ({len(only_rust)}):")
    for p in sorted(only_rust)[:10]:
        print(f"  {p}")
    if len(only_rust) > 10:
        print(f"  ... and {len(only_rust) - 10} more")

if __name__ == "__main__":
    asyncio.run(main())
