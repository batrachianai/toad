from toad._rust_fuzzy import scan_directory_parallel as rust_scan

results = rust_scan("/Users/willmcgugan/projects/external/TypeScript", False, 10.0)
root_path = "/Users/willmcgugan/projects/external/TypeScript"

# Check if root is included
if root_path in results:
    print("Root directory IS included in results")
else:
    print("Root directory is NOT included in results")

# Show first 5 results
print("\nFirst 5 results:")
for r in sorted(results)[:5]:
    print(f"  {r}")
