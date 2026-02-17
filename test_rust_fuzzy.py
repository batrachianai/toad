#!/usr/bin/env python
"""Test script to compare Rust and Python fuzzy search implementations."""

import sys
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# First add src to get the Python fuzzy module
sys.path.insert(0, os.path.join(script_dir, 'src'))
from toad.fuzzy import FuzzySearch as PyFuzzySearch

# Then add rust-fuzzy path and import the Rust module directly
sys.path.insert(0, os.path.join(script_dir, 'rust-fuzzy', 'python'))

# Import the compiled Rust module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "_rust_fuzzy", 
    os.path.join(script_dir, 'rust-fuzzy', 'python', 'toad', '_rust_fuzzy.cpython-314-darwin.so')
)
_rust_fuzzy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_rust_fuzzy_module)
FuzzySearch = _rust_fuzzy_module.FuzzySearch

def main():
    # Create both versions
    rust_fuzzy = FuzzySearch(case_sensitive=False)
    py_fuzzy = PyFuzzySearch(case_sensitive=False)

    test_cases = [
        ('foo', 'foobar'),
        ('fbr', 'foobar'),
        ('xyz', 'foobar'),
        ('test', 'this is a test'),
        ('cmd', 'CommandPalette'),
        ('cp', 'CommandPalette'),
        ('pal', 'CommandPalette'),
    ]

    print('Comparing Rust vs Python implementations:\n')
    all_match = True
    for query, candidate in test_cases:
        rust_score, rust_pos = rust_fuzzy.match_(query, candidate)
        py_score, py_pos = py_fuzzy.match(query, candidate)
        match = abs(rust_score - py_score) < 0.001 and list(rust_pos) == list(py_pos)
        all_match = all_match and match
        icon = '✓' if match else '✗'
        print(f'{icon} "{query}" in "{candidate}"')
        print(f'  Rust:   score={rust_score:.4f}, positions={rust_pos}')
        print(f'  Python: score={py_score:.4f}, positions={list(py_pos)}')
        if not match:
            print(f'  MISMATCH!')
        print()

    if all_match:
        print('✓ All tests passed! Rust and Python implementations match.')
    else:
        print('✗ Some tests failed.')
    
    return 0 if all_match else 1

if __name__ == '__main__':
    sys.exit(main())
