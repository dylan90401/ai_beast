#!/usr/bin/env python3
"""
Performance test to demonstrate improvements in file hashing.

This script compares the old approach (loading entire file into memory)
vs the new chunked approach for computing SHA256 hashes.
"""
import hashlib
import tempfile
import time
from pathlib import Path


def hash_file_old_way(path: Path) -> str:
    """Old approach: load entire file into memory."""
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def hash_file_new_way(path: Path) -> str:
    """New approach: chunk-based reading."""
    sha256_hash = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def create_test_file(size_mb: int) -> Path:
    """Create a temporary test file of specified size."""
    temp_file = Path(tempfile.mktemp(suffix='.bin'))
    # Write test data in chunks to avoid memory issues
    chunk_size = 1024 * 1024  # 1 MB
    with open(temp_file, 'wb') as f:
        for _ in range(size_mb):
            f.write(b'x' * chunk_size)
    return temp_file


def benchmark_approach(func, path: Path, runs: int = 3) -> dict:
    """Benchmark a hashing function."""
    times = []
    hash_result = None

    for _ in range(runs):
        start = time.time()
        hash_result = func(path)
        duration = time.time() - start
        times.append(duration)

    avg_time = sum(times) / len(times)
    return {
        'avg_time': avg_time,
        'hash': hash_result,
        'times': times
    }


def main():
    print("Performance Test: File Hashing Optimization")
    print("=" * 60)

    # Test with different file sizes
    test_sizes = [1, 10, 50]  # MB

    for size_mb in test_sizes:
        print(f"\nTesting with {size_mb}MB file...")
        test_file = create_test_file(size_mb)

        try:
            # Benchmark old approach
            print("  Old approach (load entire file)...", end=' ', flush=True)
            old_result = benchmark_approach(hash_file_old_way, test_file)
            print(f"{old_result['avg_time']:.3f}s")

            # Benchmark new approach
            print("  New approach (chunk-based)...", end=' ', flush=True)
            new_result = benchmark_approach(hash_file_new_way, test_file)
            print(f"{new_result['avg_time']:.3f}s")

            # Verify hashes match
            if old_result['hash'] == new_result['hash']:
                print("  ✓ Hashes match")
            else:
                print("  ✗ ERROR: Hashes don't match!")

            # Calculate improvement
            improvement = ((old_result['avg_time'] - new_result['avg_time']) /
                          old_result['avg_time'] * 100)

            if improvement > 0:
                print(f"  Performance: {improvement:.1f}% faster")
            elif improvement < 0:
                print(f"  Performance: {abs(improvement):.1f}% slower")
            else:
                print("  Performance: about the same")

            # Memory benefit note
            print(f"  Memory: Constant 8KB buffer vs {size_mb}MB file in memory")

        finally:
            # Cleanup
            test_file.unlink()

    print("\n" + "=" * 60)
    print("Key Benefits of Chunk-Based Approach:")
    print("  1. Constant memory usage (8KB) regardless of file size")
    print("  2. Better CPU cache utilization")
    print("  3. Can handle files larger than available RAM")
    print("  4. Similar or better performance for large files")


if __name__ == '__main__':
    main()
