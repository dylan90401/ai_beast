"""Integration test fixtures and configuration.

Task 2.3 - Integration test suite fixtures.
"""
import os
import shutil
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless AI_BEAST_INTEGRATION=1."""
    if os.environ.get("AI_BEAST_INTEGRATION") in ("1", "true", "True"):
        return
    skip = pytest.mark.skip(reason="Set AI_BEAST_INTEGRATION=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with full directory structure.
    
    Creates a realistic workspace layout for integration testing.
    """
    workspace = tmp_path / "ai_beast_test"
    workspace.mkdir()

    # Core directories
    dirs = [
        "config",
        "config/manifests",
        "config/resources",
        "config/secrets",
        "models",
        "models/llm",
        "models/comfyui",
        "data",
        "data/rag",
        "data/registry",
        "cache",
        "cache/llm",
        "logs",
        "outputs",
        "bin",
        "scripts",
        "scripts/lib",
    ]
    for d in dirs:
        (workspace / d).mkdir(parents=True, exist_ok=True)

    # Create mock beast CLI
    beast = workspace / "bin" / "beast"
    beast.write_text("#!/bin/bash\necho 'mock beast'")
    beast.chmod(0o755)

    # Create minimal paths.env
    paths_env = workspace / "config" / "paths.env"
    paths_env.write_text(f'''# Test paths.env
BASE_DIR="{workspace}"
MODELS_DIR="{workspace}/models"
LLM_MODELS_DIR="{workspace}/models/llm"
DATA_DIR="{workspace}/data"
CACHE_DIR="{workspace}/cache"
LOG_DIR="{workspace}/logs"
HEAVY_DIR="{workspace}"
''')

    # Create minimal state.json
    state_json = workspace / "config" / "state.json"
    state_json.write_text('{"desired": {"packs_enabled": [], "extensions_enabled": []}}')

    return workspace


@pytest.fixture
def mock_model_files(temp_workspace):
    """Create mock model files in the workspace."""
    models_dir = temp_workspace / "models" / "llm"
    
    files = [
        ("test-model-Q4_K_M.gguf", 1024 * 1024),  # 1MB
        ("llama-7b-Q8_0.gguf", 2 * 1024 * 1024),  # 2MB
        ("mistral-fp16.safetensors", 512 * 1024),  # 512KB
    ]
    
    created = []
    for name, size in files:
        path = models_dir / name
        path.write_bytes(b"0" * min(size, 1024))  # Just write 1KB for speed
        created.append(path)
    
    return created


@pytest.fixture
def mock_documents(temp_workspace):
    """Create mock documents for RAG testing."""
    docs_dir = temp_workspace / "data" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    files = {
        "readme.md": "# Test Project\n\nThis is a test document for RAG ingestion.",
        "notes.txt": "These are some plain text notes.\n\nMultiple paragraphs here.",
        "code.py": "#!/usr/bin/env python3\n\ndef hello():\n    print('Hello, World!')\n",
    }
    
    created = []
    for name, content in files.items():
        path = docs_dir / name
        path.write_text(content)
        created.append(path)
    
    return docs_dir, created


@pytest.fixture
def llm_manager(temp_workspace):
    """Create LLMManager instance with test workspace."""
    from modules.llm.manager import LLMManager
    return LLMManager(base_dir=temp_workspace)


@pytest.fixture
def docker_available():
    """Check if Docker is available."""
    return shutil.which("docker") is not None


@pytest.fixture
def ollama_available():
    """Check if Ollama is available and running."""
    import urllib.request
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:
        return False
