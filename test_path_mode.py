#!/usr/bin/env python
"""Test path mode scoring in Rust fuzzy search."""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'src'))

# Import Rust version
import importlib.util
spec = importlib.util.spec_from_file_location(
    "_rust_fuzzy", 
    os.path.join(script_dir, 'src', 'toad', '_rust_fuzzy.cpython-314-darwin.so')
)
_rust_fuzzy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_rust_fuzzy_module)

from toad.widgets.path_search import PathFuzzySearch

def test_path_mode():
    """Test that path mode treats / as word boundaries."""
    
    # Create Python version (with custom scoring)
    py_fuzzy = PathFuzzySearch(case_sensitive=False)
    
    # Create Rust version with path_mode=True
    rust_fuzzy = _rust_fuzzy_module.FuzzySearch(case_sensitive=False, path_mode=True)
    
    # Test cases for path matching
    test_cases = [
        ('src', 'src/toad/fuzzy.py'),
        ('toad', 'src/toad/fuzzy.py'),
        ('fuzzy', 'src/toad/fuzzy.py'),
        ('tf', 'src/toad/fuzzy.py'),  # toad/fuzzy
        ('stf', 'src/toad/fuzzy.py'), # src/toad/fuzzy
        ('main', 'src/main.py'),
        ('sm', 'src/main.py'),
        ('lib', 'rust-fuzzy/src/lib.rs'),
        ('rs', 'rust-fuzzy/src/lib.rs'),
    ]
    
    print("Testing Path Mode Scoring")
    print("=" * 70)
    
    all_match = True
    for query, candidate in test_cases:
        py_score, py_positions = py_fuzzy.match(query, candidate)
        rust_score, rust_positions = rust_fuzzy.match_(query, candidate)
        
        # Check if results match
        match = (abs(py_score - rust_score) < 0.001 and 
                list(py_positions) == list(rust_positions))
        
        icon = "✓" if match else "✗"
        print(f'{icon} "{query}" in "{candidate}"')
        print(f'  Python: score={py_score:.4f}, positions={list(py_positions)}')
        print(f'  Rust:   score={rust_score:.4f}, positions={list(rust_positions)}')
        
        if not match:
            print('  MISMATCH!')
            all_match = False
        print()
    
    return all_match


def test_first_letter_boost():
    """Test that path mode correctly identifies first letters."""
    
    # Python version
    py_fuzzy = PathFuzzySearch(case_sensitive=False)
    
    # Rust version with path mode
    rust_fuzzy = _rust_fuzzy_module.FuzzySearch(case_sensitive=False, path_mode=True)
    
    # This should strongly favor matches at the start of path components
    candidate = 'src/components/button.tsx'
    
    test_queries = [
        's',    # Start of path - should match position 0
        'c',    # Start of 'components' - should match after /
        'b',    # Start of 'button' - should match after /
        'scb',  # All three first letters
    ]
    
    print("\nTesting First Letter Boost (Path Components)")
    print("=" * 70)
    print(f"Candidate: {candidate}")
    print(f"First letters should be: 0 (s), 4 (c), 15 (b)\n")
    
    all_match = True
    for query in test_queries:
        py_score, py_positions = py_fuzzy.match(query, candidate)
        rust_score, rust_positions = rust_fuzzy.match_(query, candidate)
        
        match = (abs(py_score - rust_score) < 0.001 and 
                list(py_positions) == list(rust_positions))
        
        icon = "✓" if match else "✗"
        print(f'{icon} Query: "{query}"')
        print(f'  Python: score={py_score:.4f}, positions={list(py_positions)}')
        print(f'  Rust:   score={rust_score:.4f}, positions={list(rust_positions)}')
        
        if not match:
            print('  MISMATCH!')
            all_match = False
    
    return all_match


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("PATH MODE FUZZY SEARCH TEST")
    print("=" * 70 + "\n")
    
    result1 = test_path_mode()
    result2 = test_first_letter_boost()
    
    print("\n" + "=" * 70)
    if result1 and result2:
        print("✓ All path mode tests passed!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        print("=" * 70)
        sys.exit(1)
