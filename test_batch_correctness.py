#!/usr/bin/env python3
"""Test that batch matching produces identical results to sequential matching."""

from toad._rust_fuzzy import FuzzySearch as RustFuzzySearch

def test_batch_correctness():
    """Verify batch matching produces identical results to sequential."""
    
    test_cases = [
        # (query, candidates)
        ("test", [
            "test_file.py",
            "tests/unit.py",
            "src/testing.ts",
            "module_test.rs",
            "no_match.txt",
        ]),
        ("src", [
            "src/main.py",
            "src/utils/helper.ts",
            "resources/data.json",
            "scripts/deploy.sh",
        ]),
        ("fuzzy", [
            "fuzzy_search.py",
            "src/fuzzy.rs",
            "test_fuzzy.py",
            "fuzz.txt",
            "completely_different.md",
        ]),
        # Edge cases
        ("", ["file1.py", "file2.py"]),  # Empty query
        ("x", []),  # Empty candidates
        ("abc", ["abc", "abc", "abc"]),  # Duplicate candidates
    ]
    
    print("Testing batch matching correctness")
    print("=" * 70)
    
    all_passed = True
    
    for query, candidates in test_cases:
        if not candidates:
            print(f"\n✓ Query '{query}' with 0 candidates (skipped)")
            continue
            
        print(f"\nQuery: '{query}' against {len(candidates)} candidates")
        print("-" * 70)
        
        # Create two separate instances to ensure clean state
        fuzzy_sequential = RustFuzzySearch(case_sensitive=False, path_mode=True)
        fuzzy_batch = RustFuzzySearch(case_sensitive=False, path_mode=True)
        
        # Get sequential results
        sequential_results = [
            fuzzy_sequential.match_(query, candidate)
            for candidate in candidates
        ]
        
        # Get batch results
        batch_results = fuzzy_batch.match_batch(query, candidates)
        
        # Compare
        if len(sequential_results) != len(batch_results):
            print(f"  ✗ Length mismatch: {len(sequential_results)} vs {len(batch_results)}")
            all_passed = False
            continue
        
        mismatches = []
        for i, (seq, batch) in enumerate(zip(sequential_results, batch_results)):
            seq_score, seq_positions = seq
            batch_score, batch_positions = batch
            
            if abs(seq_score - batch_score) > 0.0001 or list(seq_positions) != list(batch_positions):
                mismatches.append((i, candidates[i], seq, batch))
        
        if mismatches:
            print(f"  ✗ Found {len(mismatches)} mismatches:")
            for idx, candidate, seq, batch in mismatches[:3]:  # Show first 3
                print(f"    [{idx}] '{candidate}':")
                print(f"      Sequential: score={seq[0]:.4f}, positions={list(seq[1])}")
                print(f"      Batch:      score={batch[0]:.4f}, positions={list(batch[1])}")
            all_passed = False
        else:
            print(f"  ✓ All {len(candidates)} results match perfectly")
            # Show a sample result
            if candidates and sequential_results[0][0] > 0:
                score, positions = sequential_results[0]
                print(f"    Example: '{candidates[0]}' -> score={score:.4f}, positions={list(positions)}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All batch correctness tests passed!")
        print("  Batch matching produces identical results to sequential matching.")
    else:
        print("✗ Some tests failed!")
        return False
    
    return True

def test_large_batch():
    """Test with a large batch to ensure parallel code path is exercised."""
    print("\n" + "=" * 70)
    print("Testing large batch (parallel code path)")
    print("=" * 70)
    
    # Generate 2000 paths to exceed the PARALLEL_THRESHOLD
    candidates = [f"src/module_{i}/file_{i}.py" for i in range(2000)]
    query = "file"
    
    fuzzy_sequential = RustFuzzySearch(case_sensitive=False, path_mode=True)
    fuzzy_batch = RustFuzzySearch(case_sensitive=False, path_mode=True)
    
    print(f"\nQuery: '{query}' against {len(candidates)} candidates")
    print("This should use parallel processing...")
    
    # Get results
    sequential_results = [
        fuzzy_sequential.match_(query, candidate)
        for candidate in candidates
    ]
    batch_results = fuzzy_batch.match_batch(query, candidates)
    
    # Compare
    mismatches = 0
    for i, (seq, batch) in enumerate(zip(sequential_results, batch_results)):
        seq_score, seq_positions = seq
        batch_score, batch_positions = batch
        
        if abs(seq_score - batch_score) > 0.0001 or list(seq_positions) != list(batch_positions):
            mismatches += 1
    
    if mismatches > 0:
        print(f"✗ Found {mismatches} mismatches out of {len(candidates)}")
        return False
    else:
        print(f"✓ All {len(candidates)} results match perfectly")
        # Show statistics
        matching = sum(1 for score, _ in batch_results if score > 0)
        print(f"  {matching} candidates matched the query")
        print(f"  {len(candidates) - matching} candidates did not match")
        return True

if __name__ == "__main__":
    success = test_batch_correctness()
    success = test_large_batch() and success
    
    if not success:
        exit(1)
