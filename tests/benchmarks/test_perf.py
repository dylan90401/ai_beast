"""Performance benchmarks using pytest-benchmark.

Task 2.4 - Core performance tests for AI Beast components.

Run benchmarks:
    pytest tests/benchmarks/ --benchmark-only -v
    
Generate report:
    pytest tests/benchmarks/ --benchmark-only --benchmark-autosave

Compare runs:
    pytest tests/benchmarks/ --benchmark-compare
"""
import pytest


# =============================================================================
# Text Chunking Benchmarks
# =============================================================================

@pytest.mark.benchmark(group="chunking")
def test_chunk_text_small(benchmark):
    """Benchmark: Chunk 1000 words."""
    from modules.rag.ingest import chunk_text
    
    text = "word " * 1000
    
    result = benchmark(chunk_text, text, 1200, 200)
    
    assert len(result) > 0


@pytest.mark.benchmark(group="chunking")
def test_chunk_text_medium(benchmark, large_text):
    """Benchmark: Chunk 10,000 words."""
    from modules.rag.ingest import chunk_text
    
    result = benchmark(chunk_text, large_text, 1200, 200)
    
    assert len(result) > 0
    # Should complete in reasonable time
    assert benchmark.stats["mean"] < 0.5


@pytest.mark.benchmark(group="chunking")
def test_chunk_text_large(benchmark):
    """Benchmark: Chunk 100,000 characters."""
    from modules.rag.ingest import chunk_text
    
    text = "A" * 100_000
    
    result = benchmark(chunk_text, text, 1200, 200)
    
    assert len(result) > 0


@pytest.mark.benchmark(group="chunking")
def test_chunk_text_varied_sizes(benchmark):
    """Benchmark: Chunk with different chunk sizes."""
    from modules.rag.ingest import chunk_text
    
    text = "word " * 5000
    
    def chunk_varied():
        results = []
        for size in [500, 1000, 1500, 2000]:
            results.extend(chunk_text(text, size, size // 6))
        return results
    
    result = benchmark(chunk_varied)
    assert len(result) > 0


# =============================================================================
# Model Scanning Benchmarks
# =============================================================================

@pytest.mark.benchmark(group="scanning")
def test_model_scan_empty(benchmark, benchmark_workspace):
    """Benchmark: Scan empty directory."""
    from modules.llm.manager import LLMManager
    
    manager = LLMManager(base_dir=benchmark_workspace)
    
    result = benchmark(manager.scan_local_models, force=True)
    
    assert result == []


@pytest.mark.benchmark(group="scanning")
def test_model_scan_100_files(benchmark, benchmark_workspace, many_model_files):
    """Benchmark: Scan directory with 100 model files."""
    from modules.llm.manager import LLMManager
    
    manager = LLMManager(base_dir=benchmark_workspace)
    
    result = benchmark(manager.scan_local_models, force=True)
    
    assert len(result) == 100
    # Should complete in < 1 second
    assert benchmark.stats["mean"] < 1.0


@pytest.mark.benchmark(group="scanning")
def test_model_scan_cached(benchmark, benchmark_workspace, many_model_files):
    """Benchmark: Scan with cache hit."""
    from modules.llm.manager import LLMManager
    
    manager = LLMManager(base_dir=benchmark_workspace)
    
    # Prime the cache
    manager.scan_local_models(force=True)
    
    # Benchmark cached reads
    result = benchmark(manager.scan_local_models, force=False)
    
    assert len(result) == 100
    # Cached should be very fast
    assert benchmark.stats["mean"] < 0.01


# =============================================================================
# Utility Function Benchmarks
# =============================================================================

@pytest.mark.benchmark(group="utils")
def test_human_size_benchmark(benchmark):
    """Benchmark: Human size conversion."""
    from modules.llm.manager import _human_size
    
    sizes = [100, 1024, 1024**2, 1024**3, 1024**4]
    
    def convert_all():
        return [_human_size(s) for s in sizes]
    
    result = benchmark(convert_all)
    assert len(result) == 5


@pytest.mark.benchmark(group="utils")
def test_extract_quant_benchmark(benchmark):
    """Benchmark: Quantization extraction."""
    from modules.llm.manager import _extract_quant
    
    filenames = [
        "model-Q4_K_M.gguf",
        "llama-7b-Q8_0.gguf",
        "mistral-fp16.safetensors",
        "gpt2.bin",
        "model_without_quant.gguf",
    ]
    
    def extract_all():
        return [_extract_quant(f) for f in filenames]
    
    result = benchmark(extract_all)
    assert len(result) == 5


@pytest.mark.benchmark(group="utils")
def test_validate_url_benchmark(benchmark):
    """Benchmark: URL validation."""
    from modules.llm.manager import _validate_download_url
    
    urls = [
        "https://example.com/model.gguf",
        "http://huggingface.co/model.safetensors",
        "ftp://invalid.com/file.bin",
        "https://localhost/model.gguf",
        "",
    ]
    
    def validate_all():
        return [_validate_download_url(u) for u in urls]
    
    result = benchmark(validate_all)
    assert len(result) == 5


# =============================================================================
# Hashing Benchmarks
# =============================================================================

@pytest.mark.benchmark(group="hashing")
def test_sha256_small(benchmark):
    """Benchmark: SHA256 hash of small data."""
    from modules.rag.ingest import sha256_bytes
    
    data = b"small test data"
    
    result = benchmark(sha256_bytes, data)
    
    assert len(result) == 64


@pytest.mark.benchmark(group="hashing")
def test_sha256_medium(benchmark):
    """Benchmark: SHA256 hash of 1MB data."""
    from modules.rag.ingest import sha256_bytes
    
    data = b"X" * (1024 * 1024)
    
    result = benchmark(sha256_bytes, data)
    
    assert len(result) == 64


@pytest.mark.benchmark(group="hashing")
def test_sha256_large(benchmark):
    """Benchmark: SHA256 hash of 10MB data."""
    from modules.rag.ingest import sha256_bytes
    
    data = b"X" * (10 * 1024 * 1024)
    
    result = benchmark(sha256_bytes, data)
    
    assert len(result) == 64
    # Should complete in < 1 second
    assert benchmark.stats["mean"] < 1.0


# =============================================================================
# File Iteration Benchmarks
# =============================================================================

@pytest.mark.benchmark(group="files")
def test_iter_files_benchmark(benchmark, benchmark_workspace):
    """Benchmark: Iterate over files in directory."""
    from modules.rag.ingest import iter_files
    
    # Create test files
    docs = benchmark_workspace / "docs"
    docs.mkdir()
    for i in range(50):
        (docs / f"doc_{i:03d}.txt").write_text(f"Document {i}")
        (docs / f"doc_{i:03d}.md").write_text(f"# Document {i}")
    
    def iterate():
        return list(iter_files(docs, exts=[]))
    
    result = benchmark(iterate)
    
    assert len(result) == 100
