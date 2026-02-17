# Building and Publishing Toad with Rust Binaries

## Current Situation

Right now, the Rust fuzzy search module is built locally using `make build-rust`, which:
- Only builds for your current platform (macOS ARM64)
- Copies the `.so` file to `src/toad/` for local development
- Won't be included in the published package by default

**When you publish to PyPI without multi-platform builds, users on other platforms will fall back to the pure Python implementation.**

## Publishing Options

### Option 1: GitHub Actions (Recommended) ✅

Use GitHub Actions to automatically build wheels for all platforms when you create a release.

**Platforms covered:**
- ✓ Linux x86_64 (manylinux)
- ✓ macOS x86_64 (Intel)
- ✓ macOS ARM64 (Apple Silicon)
- ✓ Windows x86_64

**Setup:**

1. The workflow file has been created at `.github/workflows/build-wheels.yml`

2. Add PyPI API token to GitHub secrets:
   - Go to PyPI → Account Settings → API tokens
   - Create token with upload permissions
   - Add to GitHub repo: Settings → Secrets → New repository secret
   - Name: `PYPI_API_TOKEN`

3. To build and publish:
   ```bash
   # Create a GitHub release
   git tag v0.6.1
   git push origin v0.6.1
   gh release create v0.6.1 --generate-notes
   
   # GitHub Actions will automatically:
   # - Build wheels for all platforms
   # - Upload to PyPI
   ```

4. To test builds without publishing:
   - Go to Actions tab in GitHub
   - Click "Build Wheels" workflow
   - Click "Run workflow"
   - Download artifacts to test locally

**Pros:**
- ✅ Fully automated
- ✅ Builds for all platforms
- ✅ No local setup needed
- ✅ Free for public repos
- ✅ Can test before publishing

**Cons:**
- ⚠️ Requires GitHub repository
- ⚠️ ~5-10 minutes per build

### Option 2: Use cibuildwheel Locally

Build all platform wheels on your local machine using Docker/cross-compilation.

**Setup:**

```bash
pip install cibuildwheel

# Build for all platforms (uses Docker for Linux, QEMU for ARM)
cd rust-fuzzy
cibuildwheel --platform linux
cibuildwheel --platform macos
cibuildwheel --platform windows
```

Add to `rust-fuzzy/pyproject.toml`:
```toml
[tool.cibuildwheel]
build = "cp310-* cp311-* cp312-* cp313-* cp314-*"
skip = "*-musllinux_*"  # Skip musl Linux builds if not needed
manylinux-x86_64-image = "manylinux2014"
```

**Pros:**
- ✅ Full control over build process
- ✅ Can test locally before publishing
- ✅ No GitHub dependency

**Cons:**
- ⚠️ Requires Docker for Linux builds
- ⚠️ Requires QEMU for cross-platform
- ⚠️ Time-consuming (30-60 mins)
- ⚠️ Complex setup

### Option 3: Source Distribution Only (Not Recommended)

Publish only the source distribution (`.tar.gz`) and let users compile Rust locally.

```bash
cd rust-fuzzy
maturin sdist --out dist
twine upload dist/*.tar.gz
```

**Pros:**
- ✅ Simple to publish
- ✅ Works for all platforms

**Cons:**
- ⚠️ Users need Rust toolchain installed
- ⚠️ Slow installation (compile time)
- ⚠️ May fail if Rust not available
- ⚠️ Poor user experience

### Option 4: Platform-Specific Wheels

Publish separate packages for each platform.

```bash
# Build on each platform
maturin build --release --interpreter python3.14

# Publish from each machine
maturin upload dist/*.whl
```

**Pros:**
- ✅ Simple if you have access to all platforms

**Cons:**
- ⚠️ Need access to Linux, macOS, Windows
- ⚠️ Manual process for each release
- ⚠️ Error-prone

## Recommended Approach

**Use Option 1 (GitHub Actions)** - it's the industry standard for Python packages with Rust extensions.

### Implementation Steps

1. **Set up GitHub Actions** (already done - `.github/workflows/build-wheels.yml`)

2. **Add PyPI token to GitHub secrets:**
   ```bash
   # On PyPI
   # Account Settings → API tokens → Create token
   # Scope: "Upload packages"
   
   # On GitHub
   # Settings → Secrets and variables → Actions → New repository secret
   # Name: PYPI_API_TOKEN
   # Value: pypi-... (your token)
   ```

3. **Update rust-fuzzy/pyproject.toml** to specify Python versions:
   ```toml
   [project]
   requires-python = ">=3.10"  # Match Toad's minimum version
   ```

4. **Ensure Rust module is optional** in main Toad package:
   
   The current code already handles this correctly:
   ```python
   try:
       from toad._rust_fuzzy import FuzzySearch as _RustFuzzySearch
       _RUST_AVAILABLE = True
   except ImportError:
       _RUST_AVAILABLE = False
   ```

5. **Test the workflow:**
   ```bash
   # Trigger manually first to test
   gh workflow run build-wheels.yml
   
   # Check the artifacts
   gh run list --workflow=build-wheels.yml
   ```

6. **Create a release to publish:**
   ```bash
   git tag v0.6.1
   git push origin v0.6.1
   gh release create v0.6.1 --generate-notes
   
   # Workflow runs automatically
   # Check progress:
   gh run watch
   ```

## What Users Will Get

### When Binary Wheel Available (After GitHub Actions Build)

```bash
pip install batrachian-toad
# Downloads pre-built wheel for their platform
# Rust fuzzy search is immediately available
# Fast installation (no compilation)
```

### When Binary Wheel Not Available

```bash
pip install batrachian-toad
# Downloads source distribution
# Falls back to pure Python implementation
# Rust not available but everything still works
```

The package gracefully degrades to Python if Rust isn't available!

## Platform Coverage

With the GitHub Actions workflow, you'll publish wheels for:

| Platform | Python Versions | Notes |
|----------|----------------|-------|
| Linux x86_64 | 3.10, 3.11, 3.12, 3.13, 3.14 | manylinux wheels (compatible with most distros) |
| macOS x86_64 | 3.10, 3.11, 3.12, 3.13, 3.14 | Intel Macs |
| macOS ARM64 | 3.10, 3.11, 3.12, 3.13, 3.14 | Apple Silicon Macs |
| Windows x86_64 | 3.10, 3.11, 3.12, 3.13, 3.14 | 64-bit Windows |

**Total: ~20 wheel files per release**

## Integrating into Main Package

Currently, the Rust module is separate. You have two options:

### Option A: Keep Separate (Current)

- Main package: `batrachian-toad` (pure Python + optional Rust)
- Rust extension: Separate build/publish (as shown above)
- Users install: `pip install batrachian-toad` (includes Rust if wheel available)

### Option B: Integrate into Main Package

Merge rust-fuzzy into the main Toad build system:

1. Move `rust-fuzzy/` to `src/toad/_rust_fuzzy/`
2. Update main `pyproject.toml`:
   ```toml
   [build-system]
   requires = ["maturin>=1.0,<2.0"]
   build-backend = "maturin"
   ```
3. Single package, single publish process

**Recommendation:** Keep separate for now. It's cleaner and allows independent versioning.

## Verifying the Build

After publishing, test on a fresh environment:

```bash
# Create fresh venv
python3.14 -m venv test-env
source test-env/bin/activate

# Install from PyPI
pip install batrachian-toad==0.6.1

# Check if Rust is available
python -c "from toad._rust_fuzzy import FuzzySearch; print('Rust available!')"

# If error: Rust wheel not available for your platform (using Python fallback)
# If success: Rust binary was installed correctly
```

## Troubleshooting

### "No matching distribution found"
- Wheel not built for your platform/Python version
- Falls back to source distribution
- Requires Rust to compile

**Solution:** Expand Python version range in workflow

### "Failed to build rust-fuzzy"
- Source distribution compilation failed
- User doesn't have Rust installed

**Solution:** Ensure fallback to Python works:
```python
# This should never fail even without Rust
from toad.fuzzy import FuzzySearch
```

### Wheel file size too large
- Each wheel is ~500KB-2MB
- 20 wheels = ~10-40MB total

**Solution:** Normal for Rust extensions. PyPI allows up to 100MB per file.

## Summary

**Recommended Setup:**

1. ✅ Use GitHub Actions workflow (provided)
2. ✅ Add PyPI token to GitHub secrets
3. ✅ Create releases with `gh release create v0.6.1`
4. ✅ Wheels automatically built and published
5. ✅ Users get fast Rust version on all major platforms
6. ✅ Automatic fallback to Python if wheel unavailable

**Result:** Users on Linux, macOS, and Windows get the 7-16x faster Rust implementation with zero setup, while others get a working Python fallback.
