"""Compare files found by Rust vs Python implementations."""
import asyncio
from pathlib import Path
from toad.directory import scan
from toad.path_filter import PathFilter
from toad._rust_fuzzy import scan_directory_parallel as rust_scan

async def main():
    scan_path = Path("/Users/willmcgugan/projects/external/TypeScript")
    path_filter = PathFilter.from_git_root(scan_path)
    
    # Python scan (with max_duration to match benchmark)
    print("Running Python scan...")
    python_paths = await scan(scan_path, path_filter=path_filter, max_duration=10.0)
    python_set = set(str(p) for p in python_paths)
    print(f"Python found: {len(python_set)} files")
    
    # Rust scan (calls directly, which then applies filter in Python)
    print("Running Rust scan through scan()...")
    rust_paths_filtered = await scan(scan_path, path_filter=path_filter, max_duration=10.0)
    
    # Disable Python filtering temporarily to see raw Rust output
    import toad.directory as dir_mod
    original = dir_mod._RUST_AVAILABLE
    dir_mod._RUST_AVAILABLE = False
    python_paths2 = await scan(scan_path, path_filter=path_filter, max_duration=10.0)
    dir_mod._RUST_AVAILABLE = original
    
    print(f"Python (no Rust): {len(python_paths2)} files")
    print(f"Rust (with Python filter): {len(rust_paths_filtered)} files")
    
    # Direct Rust call
    rust_direct = rust_scan(str(scan_path), False, 10.0)
    print(f"Rust (direct, no filter): {len(rust_direct)} files")

if __name__ == "__main__":
    asyncio.run(main())
