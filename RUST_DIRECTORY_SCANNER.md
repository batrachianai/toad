# Rust Directory Scanner Implementation

## Overview

A high-performance parallel directory scanner implemented in Rust, providing significant speedups for scanning large directory trees.

## Implementation

### Rust Core (`rust-fuzzy/src/lib.rs`)

```rust
#[pyfunction]
fn scan_directory_parallel(
    root: String,
    add_directories: bool,
    max_duration: Option<f64>,
) -> PyResult<Vec<String>>
```

**Features:**
- Parallel scanning using multiple worker threads
- Work-stealing queue for load balancing
- Atomic counters for termination detection
- Timeout support
- Returns list of path strings

### Python Wrapper (`src/toad/directory.py`)

The Python `scan()` function automatically uses the Rust implementation when available:

```python
async def scan(
    root: Path,
    *,
    max_simultaneous: int = 5,
    path_filter: PathFilter | None = None,
    add_directories: bool = False,
    max_duration: float | None = 5.0,
) -> list[Path]:
    # Uses Rust if available, falls back to Python
    ...
```

## Performance

### Test Case: Textual Project (~8000 files)

```
Scanned 7952 paths in 0.44s
```

Compared to Python's async implementation, the Rust version provides:
- **Parallel scanning** across multiple CPU cores
- **Lock-free work distribution** using crossbeam channels
- **Efficient termination** detection with atomic counters

## Current Limitations

### Path Filtering

The current implementation applies `PathFilter` in Python **after** Rust completes the scan:

```python
# Rust scans everything
path_strings = await asyncio.to_thread(_rust_scan, ...)

# Python filters afterward  
if path_filter is not None:
    paths = [p for p in paths if not path_filter.match(p)]
```

**Implication:** The scanner still traverses `.git` directories and other filtered paths, though it's still faster than the pure Python version.

**Future Enhancement:** Pass filter rules to Rust to skip filtered directories entirely.

## Architecture

### Work-Stealing Pattern

```
Main Thread
   ↓
[Send root directory to queue]
   ↓
Worker Threads (8 max)
   ├─ Thread 1: Process dirs, add subdirs to queue
   ├─ Thread 2: Process dirs, add subdirs to queue  
   ├─ Thread 3: Process dirs, add subdirs to queue
   └─ ...
   ↓
[Atomic counter tracks active tasks]
   ↓
[All workers exit when counter reaches 0]
   ↓
Return Results
```

### Synchronization

**Active Task Counter:**
```rust
// Start with 1 (root directory)
active_tasks.fetch_add(1, AtomicOrdering::SeqCst);

// When processing a directory:
active_tasks.fetch_add(num_subdirs, AtomicOrdering::SeqCst);  // Add work
// ... process directory ...
active_tasks.fetch_sub(1, AtomicOrdering::SeqCst);  // Mark complete

// Workers exit when counter reaches 0
if active_tasks.load(AtomicOrdering::SeqCst) == 0 {
    break;
}
```

This ensures all workers know when scanning is complete without requiring explicit signaling.

## API Usage

### Basic Scan

```python
from pathlib import Path
from toad.directory import scan

paths = await scan(Path("/some/directory"))
```

### With Path Filter

```python
from toad.path_filter import PathFilter

path_filter = PathFilter.from_git_root(Path("."))
paths = await scan(
    Path("."),
    path_filter=path_filter,
    max_duration=5.0
)
```

### Include Directories

```python
paths = await scan(
    Path("."),
    add_directories=True  # Include directory paths in results
)
```

## Fallback Behavior

The implementation gracefully falls back to pure Python if:
- Rust extension not available
- Any error occurs during Rust scanning

```python
try:
    # Try Rust implementation
    path_strings = await asyncio.to_thread(_rust_scan, ...)
    return [Path(p) for p in path_strings]
except Exception:
    # Fall back to Python
    # ... Python implementation ...
```

This ensures the feature works everywhere, with performance benefits where Rust is available.

## Future Enhancements

### 1. Native Path Filtering

Pass gitignore patterns to Rust to avoid scanning filtered directories:

```rust
fn scan_directory_parallel(
    root: String,
    patterns: Vec<String>,  // gitignore patterns
    add_directories: bool,
    max_duration: Option<f64>,
) -> PyResult<Vec<String>>
```

**Benefit:** Skip `.git`, `node_modules`, etc. entirely instead of scanning then filtering.

### 2. Incremental Results

Stream results back to Python as they're found:

```python
async for batch in scan_incremental(root):
    # Process paths as they're discovered
    process(batch)
```

**Benefit:** Start processing files before scan completes.

### 3. Symlink Handling

Add options for symlink behavior:
- Follow symlinks
- Skip symlinks
- Detect cycles

### 4. File Metadata

Return additional information:
- File size
- Modification time
- File type

```rust
struct FileInfo {
    path: String,
    size: u64,
    modified: u64,
    is_dir: bool,
}
```

## Dependencies

- `crossbeam-channel`: Lock-free MPMC channels for work distribution
- `rayon`: Thread pool management
- `std::sync::atomic`: Atomic counters for synchronization

## Testing

```bash
# Test basic functionality
python -c "
import asyncio
from pathlib import Path
from toad.directory import scan

async def test():
    paths = await scan(Path('src'), max_duration=2.0)
    print(f'Found {len(paths)} paths')

asyncio.run(test())
"

# Test with path filter
python -c "
import asyncio
from pathlib import Path
from toad.directory import scan
from toad.path_filter import PathFilter

async def test():
    filter = PathFilter.from_git_root(Path('.'))
    paths = await scan(Path('.'), path_filter=filter, max_duration=5.0)
    print(f'Found {len(paths)} paths (filtered)')

asyncio.run(test())
"
```

## Conclusion

The Rust directory scanner provides significant performance improvements through parallel processing while maintaining full API compatibility with the Python implementation. The automatic fallback ensures reliability across all platforms.

**Key Benefits:**
- ✓ Parallel scanning across CPU cores
- ✓ Work-stealing for load balancing
- ✓ Automatic fallback to Python
- ✓ Drop-in replacement (no code changes needed)
- ✓ Timeout support
- ✓ Thread-safe result collection

**Performance:** ~0.44s for 8000 files vs several seconds in pure Python for large projects.
