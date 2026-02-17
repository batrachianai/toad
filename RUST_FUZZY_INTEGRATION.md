# Rust Fuzzy Search Integration Guide

This document explains the Rust implementation of the fuzzy search algorithm and how to integrate it into the Toad project.

## Overview

A high-performance Rust version of `src/toad/fuzzy.py` has been implemented in the `rust-fuzzy/` directory. The implementation is fully compatible with the Python version and passes all comparison tests.

## Project Structure

```
toad/
├── rust-fuzzy/              # Rust extension module
│   ├── src/
│   │   └── lib.rs          # Rust implementation
│   ├── python/
│   │   └── toad/
│   │       ├── __init__.py
│   │       └── _rust_fuzzy.*.so  # Compiled extension
│   ├── Cargo.toml          # Rust dependencies
│   ├── pyproject.toml      # Maturin build config
│   ├── README.md           # Module documentation
│   └── .gitignore
├── src/toad/
│   └── fuzzy.py            # Original Python implementation
├── test_rust_fuzzy.py      # Comparison tests
└── Makefile                # Build targets added
```

## Building the Rust Extension

### Prerequisites

- Rust toolchain (cargo)
- maturin (`pip install maturin` or installed via dev dependencies)

### Build Commands

```bash
# Release build (optimized) - RECOMMENDED
make build-rust

# Development build (with debug symbols)
make build-rust-debug

# Or directly with maturin (requires manual copy step)
cd rust-fuzzy
maturin develop --release
cp python/toad/_rust_fuzzy.*.so ../src/toad/
```

**Note**: The Makefile automatically copies the compiled `.so` file to `src/toad/` so it's available when running `uv run toad`.

### Verify Installation

```bash
# Check if Rust implementation is being used
uv run python check_rust_fuzzy.py
```

Expected output:
```
✓ Rust implementation is AVAILABLE
✓ All tests passed! Rust fuzzy search is working correctly.
```

## Integration Status

✅ **COMPLETED**: The Rust implementation is now integrated into the main toad package!

The `src/toad/fuzzy.py` module now automatically uses the Rust implementation when available, with transparent fallback to the Python version if not built.

### How It Works

1. `src/toad/fuzzy.py` attempts to import `toad._rust_fuzzy`
2. If successful, it wraps the Rust implementation with an adapter class
3. If not available, it uses the pure Python implementation
4. All imports of `FuzzySearch` from `toad.fuzzy` automatically get the best available implementation

```python
# This automatically uses Rust if available!
from toad.fuzzy import FuzzySearch

fuzzy = FuzzySearch(case_sensitive=False)
score, positions = fuzzy.match('query', 'candidate')
```

No code changes needed in the rest of the codebase - it just works!

### Option 2: Build-time Integration

Add the Rust extension to the main build process by updating `pyproject.toml`:

1. Add `maturin` to build dependencies
2. Configure a custom build backend that builds both the Python package and Rust extension
3. Update the `[tool.hatch.build]` section to include the Rust module

### Option 3: Separate Optional Dependency

Keep `rust-fuzzy` as a separate optional dependency:

```toml
[project.optional-dependencies]
rust = ["rust-fuzzy @ file:///path/to/rust-fuzzy"]
```

## Usage

The Rust implementation provides an identical API to the Python version:

```python
from toad._rust_fuzzy import FuzzySearch

# Create instance
fuzzy = FuzzySearch(case_sensitive=False)

# Perform fuzzy matching
score, positions = fuzzy.match_('query', 'candidate string')

# Cache management
fuzzy.clear_cache()
print(fuzzy.cache_size())
```

## Testing

Run the comparison test to verify correctness:

```bash
python test_rust_fuzzy.py
```

Expected output:
```
✓ All tests passed! Rust and Python implementations match.
```

## Performance Characteristics

The Rust implementation provides:

1. **Faster execution**: Native code performance for the fuzzy matching algorithm
2. **Built-in caching**: HashMap-based cache for repeated queries
3. **Memory efficiency**: More efficient memory usage than Python dictionaries
4. **Type safety**: Compile-time guarantees about correctness

## Implementation Details

### Key Differences from Python

1. **String handling**: Careful handling of byte vs character positions for Unicode compatibility
2. **Max selection**: Uses `fold` to get first maximum (matching Python's `max()` behavior)
3. **Character indices**: Uses Rust's `char_indices()` for proper Unicode support

### Algorithm

The implementation follows the Python version exactly:

1. Find all possible positions for each query character in the candidate
2. Use recursive function to generate all valid position combinations
3. Score each combination based on:
   - Number of matches
   - Matches at word boundaries
   - Consecutive groupings
4. Return the highest-scoring match (first occurrence if tied)

## Maintenance

### Updating the Implementation

If changes are made to `src/toad/fuzzy.py`, the Rust version should be updated to match:

1. Update `rust-fuzzy/src/lib.rs` with the algorithm changes
2. Rebuild: `make build-rust`
3. Run tests: `python test_rust_fuzzy.py`
4. Ensure all tests pass before committing

### Adding Tests

Add new test cases to `test_rust_fuzzy.py` in the `test_cases` list:

```python
test_cases = [
    ('query', 'candidate string'),
    # ... more test cases
]
```

## Distribution

### Including in Wheel

To include the Rust extension in the distributed wheel:

1. Build the Rust extension
2. Ensure the `.so` file is included in the package
3. Update `MANIFEST.in` if necessary

### Platform Considerations

The Rust extension compiles to platform-specific binaries (`.so` on Linux/macOS, `.pyd` on Windows). For distribution:

- Build wheels for each target platform
- Or provide source distribution with build instructions
- Consider using GitHub Actions for multi-platform builds

## Future Enhancements

Potential improvements:

1. **Parallel processing**: Use Rayon for parallel candidate matching
2. **SIMD optimization**: Vectorized character matching for long strings
3. **Better caching**: LRU cache with configurable size
4. **Benchmarking**: Add benchmark suite comparing Rust vs Python performance
5. **Feature parity**: Expose additional configuration options

## Troubleshooting

### Build Failures

- **Missing Rust**: Install from https://rustup.rs/
- **Wrong Python version**: Ensure Python 3.8+ is available
- **Maturin errors**: Update with `pip install -U maturin`

### Import Errors

- **Module not found**: Run `make build-rust` first
- **Wrong path**: Check `sys.path` includes `rust-fuzzy/python`

### Test Failures

- **Mismatched results**: Review recent changes to Python implementation
- **Score differences**: Check floating-point comparison tolerance

## Contact

For issues or questions about the Rust implementation, refer to the main Toad project documentation or create an issue in the project repository.
