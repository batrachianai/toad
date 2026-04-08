#!/usr/bin/env bash
set -euo pipefail

uv tool install "${PWD}" --force --reinstall --quiet

# Verify installed binaries
if ! command -v canon >/dev/null 2>&1; then
  bin_dir="$(uv tool dir --bin)"
  echo "error: canon is not on PATH after install."
  echo "Add the uv tool bin directory to your PATH:"
  echo ""
  echo "  export PATH=\"${bin_dir}:\$PATH\""
  echo ""
  echo "Add this line to your shell profile (~/.zshrc, ~/.bashrc, etc.)"
  exit 1
fi

canon_version="$(canon --version 2>&1)"

if command -v canon-ctl >/dev/null 2>&1; then
  echo "canon installed (${canon_version}) — run 'canon' from any project directory"
else
  echo "canon installed (${canon_version}) — run 'canon' from any project directory"
  echo "warning: canon-ctl not found on PATH (optional but recommended)"
fi
