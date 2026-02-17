#!/usr/bin/env python
"""Check if the Rust fuzzy search implementation is being used."""

from toad.fuzzy import FuzzySearch
from toad import fuzzy

def main():
    print("Toad Fuzzy Search Implementation Check")
    print("=" * 50)
    
    # Check which implementation is available
    if fuzzy._RUST_AVAILABLE:
        print("✓ Rust implementation is AVAILABLE")
    else:
        print("✗ Rust implementation is NOT available")
        print("  Run 'make build-rust' to build it")
        return 1
    
    # Create instance and test
    fuzzy_search = FuzzySearch(case_sensitive=False)
    print(f"\nUsing: {type(fuzzy_search).__name__}")
    
    # Run a quick test
    test_cases = [
        ('foo', 'foobar', 8.0, [0, 1, 2]),
        ('cmd', 'CommandPalette', 4.4444, [0, 2, 6]),
    ]
    
    print("\nRunning tests:")
    all_passed = True
    for query, candidate, expected_score, expected_positions in test_cases:
        score, positions = fuzzy_search.match(query, candidate)
        passed = (abs(score - expected_score) < 0.001 and 
                 list(positions) == expected_positions)
        status = "✓" if passed else "✗"
        print(f"  {status} '{query}' in '{candidate}': score={score:.2f}, positions={list(positions)}")
        all_passed = all_passed and passed
    
    if all_passed:
        print("\n✓ All tests passed! Rust fuzzy search is working correctly.")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
