"""Benchmark fixtures and configuration.

Task 2.4 - Shared fixtures for performance benchmarks.
"""
import pytest
from pathlib import Path


@pytest.fixture
def benchmark_workspace(tmp_path):
    """Create workspace for benchmarking."""
    workspace = tmp_path / "bench"
    workspace.mkdir()
    
    dirs = ["config", "models", "models/llm", "cache", "cache/llm", "data"]
    for d in dirs:
        (workspace / d).mkdir(parents=True, exist_ok=True)
    
    # Minimal paths.env
    (workspace / "config" / "paths.env").write_text(f'''
BASE_DIR="{workspace}"
MODELS_DIR="{workspace}/models"
LLM_MODELS_DIR="{workspace}/models/llm"
CACHE_DIR="{workspace}/cache"
''')
    
    return workspace


@pytest.fixture
def large_text():
    """Generate large text for chunking benchmarks."""
    # 10,000 words of lorem ipsum-like text
    words = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur", 
             "adipiscing", "elit", "sed", "do", "eiusmod", "tempor"]
    import random
    random.seed(42)  # Reproducible
    return " ".join(random.choices(words, k=10000))


@pytest.fixture
def many_model_files(benchmark_workspace):
    """Create many mock model files for scanning benchmarks."""
    models_dir = benchmark_workspace / "models" / "llm"
    
    for i in range(100):
        (models_dir / f"model_{i:03d}.gguf").write_bytes(b"0" * 1024)
    
    return models_dir
