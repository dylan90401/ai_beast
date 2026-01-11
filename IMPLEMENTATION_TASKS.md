# AI Beast / Kryptos - Comprehensive Implementation Tasks
## For VS Code Copilot / GitHub Codex Execution

**Last Updated:** 2026-01-09
**Priority Levels:** P0 (Critical), P1 (High), P2 (Medium), P3 (Low)
**Complexity:** S (Small: <2hr), M (Medium: 2-8hr), L (Large: 8-24hr), XL (Extra Large: 1-3 days)

---

## PHASE 1: CRITICAL BUG FIXES & SECURITY (P0)

### Task 1.1: Fix Dependency Typo [P0, S]
**File:** `requirements.txt`
**Issue:** Typo `quartc` should be `quart`
**Impact:** Installation completely fails
**Status:** ✅ FIXED

```python
# Current (BROKEN):
quartc>=0.10.0

# Fix to:
quart>=0.10.0
```

**Verification:**
```bash
./.venv/bin/python -m pip install -r requirements.txt
# Should succeed without errors
```

**Related Files:**
- requirements.txt

---

### Task 1.2: Fix Python Version Inconsistency [P0, S]
**Files:** `pyproject.toml`
**Issue:** Python version requirement mismatch
**Status:** ✅ FIXED

```toml
# Fixed:
[project]
requires-python = ">=3.12"

[tool.ruff]
target-version = "py312"
```

**Verification:**
```bash
python3 --version  # Should be >= 3.12
./.venv/bin/python -m ruff check .
```

**Related Files:**
- pyproject.toml

---

### Task 1.3: Fix Makefile Python References [P0, S]
**File:** `Makefile`
**Issue:** Make targets must not rely on ambiguous `python`
**Status:** ✅ FIXED

**Lines to fix:**
- Line 61: `lint` target
- Line 65: `fmt` target
- Line 68: `test` target
- Line 52: `verify` target

```makefile
# Current:
lint:
    python -m ruff check .

fmt:
    python -m ruff format .

test:
    python -m pytest -q

verify:
    python scripts/00_verify_stack.py --verbose

# Fix to:
lint:
    $(PY) -m ruff check .

fmt:
    $(PY) -m ruff format .

test:
    $(PY) -m pytest -q

verify:
    $(PY) scripts/00_verify_stack.py --verbose
```

**Verification:**
```bash
make lint
make fmt
make test
make verify
```

**Related Files:**
- Makefile

---

### Task 1.4: Fix Path Traversal Vulnerability [P0, M]
**File:** `modules/llm/manager.py:456-464`
**CVE Risk:** High - Path traversal via symlink attack

**Current vulnerable code:**
```python
def delete_local_model(self, path: str) -> dict:
    fp = Path(path)
    # Safety check: only delete from known model directories
    allowed_parents = [self.llm_models_dir, self.models_dir, self.heavy_dir]
    if not any(str(fp).startswith(str(p)) for p in allowed_parents):
        return {"ok": False, "error": "Path not in allowed model directories"}
```

**Fix:**
```python
def delete_local_model(self, path: str) -> dict:
    """Delete a local model file with path traversal protection.

    Args:
        path: Path to model file to delete

    Returns:
        Dict with 'ok' and optional 'error' keys
    """
    try:
        # Resolve symlinks and normalize path
        fp = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as e:
        return {"ok": False, "error": f"Invalid path: {e}"}

    # Validate path is under allowed parents
    allowed_parents = [
        self.llm_models_dir.resolve(),
        self.models_dir.resolve(),
        self.heavy_dir.resolve()
    ]

    if not any(fp.is_relative_to(p) for p in allowed_parents):
        return {"ok": False, "error": "Path not in allowed model directories"}

    if not fp.exists():
        return {"ok": False, "error": "File not found"}

    # Additional safety: Ensure it's a file, not directory
    if not fp.is_file():
        return {"ok": False, "error": "Path is not a file"}

    try:
        fp.unlink()
        self._model_cache.pop(str(fp), None)
        self._cache_time = 0
        return {"ok": True, "path": str(fp)}
    except OSError as e:
        return {"ok": False, "error": str(e)}
```

**Testing:**
```python
# Add to tests/test_security.py
def test_path_traversal_protection(tmp_path):
    """Test: Path traversal attacks are blocked"""
    manager = LLMManager(base_dir=tmp_path)

    # Create model file
    model_dir = tmp_path / "models" / "llm"
    model_dir.mkdir(parents=True)
    model_file = model_dir / "test.gguf"
    model_file.write_text("test")

    # Valid deletion should work
    result = manager.delete_local_model(str(model_file))
    assert result["ok"]

    # Symlink attack should fail
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("secret")

    symlink = model_dir / "evil.gguf"
    symlink.symlink_to(secret_file)

    # This should fail even though symlink is in allowed dir
    result = manager.delete_local_model(str(symlink))
    assert not result["ok"]
    assert secret_file.exists()  # Secret not deleted
```

**Related Files:**
- modules/llm/manager.py
- tests/test_security.py (new)

---

### Task 1.5: Add URL Validation for Downloads [P0, M]
**File:** `modules/llm/manager.py:316-335`
**Issue:** No URL validation before download

**Current code:**
```python
def download_from_url(
    self,
    url: str,
    filename: str | None = None,
    ...
) -> dict:
    # Determine filename
    if not filename:
        filename = url.split("/")[-1].split("?")[0]
```

**Fix - Add validation function:**
```python
import urllib.parse

def _validate_download_url(self, url: str) -> tuple[bool, str]:
    """Validate URL for download safety.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Parse URL
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"Invalid URL: {e}"

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme: {parsed.scheme}"

    # Check host
    if not parsed.netloc:
        return False, "URL missing host"

    # Block localhost/internal IPs (SSRF protection)
    if parsed.netloc in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return False, "Cannot download from localhost"

    if parsed.netloc.startswith("192.168.") or parsed.netloc.startswith("10."):
        return False, "Cannot download from private network"

    # Check for suspicious patterns
    if ".." in parsed.path or parsed.path.startswith("/etc/"):
        return False, "Suspicious path in URL"

    return True, ""

def download_from_url(
    self,
    url: str,
    filename: str | None = None,
    destination: ModelLocation = ModelLocation.INTERNAL,
    custom_path: str | None = None,
    callback: Callable[[dict], None] | None = None,
    max_size_bytes: int = 50 * 1024 * 1024 * 1024,  # 50GB default limit
) -> dict:
    """Download a model from URL with validation.

    Args:
        url: URL to download from
        filename: Optional filename (extracted from URL if not provided)
        destination: Where to save (INTERNAL, EXTERNAL, CUSTOM)
        custom_path: Required if destination is CUSTOM
        callback: Progress callback function
        max_size_bytes: Maximum allowed file size (default 50GB)

    Returns:
        dict with 'ok', 'path', 'error' keys
    """
    # Validate URL
    valid, error = self._validate_download_url(url)
    if not valid:
        return {"ok": False, "error": error}

    # Determine filename with sanitization
    if not filename:
        filename = url.split("/")[-1].split("?")[0]
        if not filename or filename == "":
            filename = f"model_{int(time.time())}.gguf"

    # Sanitize filename
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    if filename.startswith('.'):
        filename = '_' + filename[1:]

    # Validate file extension
    valid_extensions = {'.gguf', '.safetensors', '.bin', '.pt', '.pth', '.onnx'}
    if not any(filename.lower().endswith(ext) for ext in valid_extensions):
        return {"ok": False, "error": f"Invalid file extension. Allowed: {valid_extensions}"}

    # ... rest of existing code ...

    def _download():
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "AI-Beast/1.0")

            with urllib.request.urlopen(req, timeout=60) as resp:
                # Check Content-Length BEFORE downloading
                total = int(resp.headers.get("Content-Length", 0))
                if total > max_size_bytes:
                    raise RuntimeError(
                        f"File too large: {total} bytes (max: {max_size_bytes})"
                    )

                # Validate Content-Type
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    raise RuntimeError(
                        "URL returned HTML instead of file (check URL)"
                    )

                downloaded = 0
                with open(temp_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Safety check during download
                        if downloaded > max_size_bytes:
                            raise RuntimeError(
                                f"Download exceeded size limit: {max_size_bytes}"
                            )

                        # ... progress tracking ...
```

**Testing:**
```python
# Add to tests/test_security.py
def test_url_validation():
    """Test: Malicious URLs are rejected"""
    manager = LLMManager()

    # Test invalid schemes
    assert not manager._validate_download_url("file:///etc/passwd")[0]
    assert not manager._validate_download_url("ftp://example.com/model.gguf")[0]

    # Test SSRF protection
    assert not manager._validate_download_url("http://localhost:8000/model.gguf")[0]
    assert not manager._validate_download_url("http://127.0.0.1/model.gguf")[0]
    assert not manager._validate_download_url("http://192.168.1.1/model.gguf")[0]

    # Test valid URLs
    assert manager._validate_download_url("https://huggingface.co/model.gguf")[0]
    assert manager._validate_download_url("http://example.com/model.safetensors")[0]
```

**Related Files:**
- modules/llm/manager.py
- tests/test_security.py

---

### Task 1.6: Audit Shell Scripts for Injection Risks [P0, L]
**Files:** All 60+ scripts in `scripts/` directory
**Issue:** Potential command injection via unquoted variables

**Scripts requiring audit (from grep results):**
1. scripts/10_init_wizard.sh
2. scripts/81_restore.sh
3. scripts/81_comfyui_nodes_install.sh
4. scripts/95_dev_setup.sh
5. scripts/13_trust.sh
6. scripts/13_features_sync.sh
7. scripts/32_status.sh
8. scripts/14_trust_enforce_asset.sh
9. scripts/17_agent_verify.sh
10. scripts/40_healthcheck.sh
11. scripts/60_restore.sh
12. scripts/95_drift.sh
13. scripts/05_manifest.sh
14. scripts/01_enable_profile.sh
15. scripts/80_packs.sh
16. scripts/34_urls.sh
17. scripts/85_extensions.sh
18. scripts/98_plan_reasoned.sh
19. scripts/16_custom_nodes_audit.sh
20. scripts/97_graph_typed.sh

**Pattern to find:**
```bash
# UNSAFE patterns:
eval "$VARIABLE"
$($COMMAND)
echo "$INPUT" | sh

# Quote all variables:
"$VARIABLE"
"${VARIABLE}"

# Validate inputs before use:
if [[ "$VAR" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    # Safe to use
fi
```

**Example fix template:**
```bash
# BEFORE (UNSAFE):
#!/usr/bin/env bash
PACK_NAME="$1"
docker exec comfyui python -c "import $PACK_NAME"

# AFTER (SAFE):
#!/usr/bin/env bash
set -euo pipefail

PACK_NAME="$1"

# Validate input
if [[ ! "$PACK_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "ERROR: Invalid pack name: $PACK_NAME" >&2
    exit 1
fi

# Quote variable
docker exec comfyui python -c "import ${PACK_NAME}"
```

**Create validation library:**
```bash
# scripts/lib/validation.sh
#!/usr/bin/env bash

# Validate alphanumeric with dashes/underscores
validate_name() {
    local name="$1"
    if [[ ! "$name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        return 1
    fi
    return 0
}

# Validate path (no traversal)
validate_path() {
    local path="$1"
    if [[ "$path" =~ \.\. ]] || [[ "$path" == *"~"* ]]; then
        return 1
    fi
    return 0
}

# Validate URL
validate_url() {
    local url="$1"
    if [[ ! "$url" =~ ^https?:// ]]; then
        return 1
    fi
    return 0
}
```

**Testing:**
```bash
# Add to tests/test_security_scripts.sh
#!/usr/bin/env bash
set -euo pipefail

# Test injection attempts
test_injection_protection() {
    local result

    # Attempt command injection
    result=$(./scripts/80_packs.sh "evil; rm -rf /" 2>&1 || true)

    # Should fail validation, not execute rm
    if [[ "$result" =~ "Invalid" ]]; then
        echo "✓ Injection protection works"
    else
        echo "✗ Injection protection FAILED"
        exit 1
    fi
}

test_injection_protection
```

**Related Files:**
- scripts/*.sh (all)
- scripts/lib/validation.sh (new)
- tests/test_security_scripts.sh (new)

---

## PHASE 2: TESTING & QUALITY IMPROVEMENTS (P1)

### Task 2.1: Install Missing Test Dependencies [P1, S]
**Issue:** pytest, ruff, pyyaml not installed

```bash
# Add to requirements-dev.txt (already correct, but verify):
ruff>=0.1.0
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
hypothesis>=6.82.0

# Install:
./.venv/bin/python -m pip install -r requirements-dev.txt

# Verify:
./.venv/bin/python -m pytest --version
./.venv/bin/python -m ruff --version
```

**Related Files:**
- requirements-dev.txt

---

### Task 2.2: Add Property-Based Testing [P1, M]
**New File:** `tests/test_properties.py`

```python
"""Property-based tests using Hypothesis."""

from hypothesis import given, strategies as st
import pytest

from modules.rag.ingest import chunk_text
from modules.llm.manager import _extract_quant, _human_size


@given(
    text=st.text(min_size=1, max_size=10000),
    chunk_size=st.integers(min_value=100, max_value=2000),
    overlap=st.integers(min_value=0, max_value=500)
)
def test_chunk_text_properties(text, chunk_size, overlap):
    """Property: All chunks should be <= chunk_size."""
    # Skip if overlap >= chunk_size (invalid)
    if overlap >= chunk_size:
        return

    chunks = chunk_text(text, chunk_size, overlap)

    # Property 1: All chunks within size limit
    assert all(len(chunk) <= chunk_size for chunk in chunks)

    # Property 2: Non-empty text produces at least one chunk
    if text.strip():
        assert len(chunks) > 0

    # Property 3: All chunks are non-empty strings
    assert all(isinstance(chunk, str) and chunk.strip() for chunk in chunks)


@given(size=st.integers(min_value=0, max_value=10**15))
def test_human_size_properties(size):
    """Property: Human-readable size is always valid."""
    result = _human_size(size)

    # Property 1: Result is non-empty string
    assert isinstance(result, str)
    assert len(result) > 0

    # Property 2: Contains a unit
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    assert any(unit in result for unit in units)

    # Property 3: Contains a number
    assert any(char.isdigit() for char in result)


@given(filename=st.text(min_size=1, max_size=100))
def test_extract_quant_safety(filename):
    """Property: Quantization extraction never crashes."""
    # Should never raise exception
    result = _extract_quant(filename)

    # Result is always a string (possibly empty)
    assert isinstance(result, str)

    # If found, should be uppercase
    if result:
        assert result.isupper()
```

**Related Files:**
- tests/test_properties.py (new)
- requirements-dev.txt (add hypothesis)

---

### Task 2.3: Add Integration Test Suite [P1, L]
**New Directory:** `tests/integration/`

```python
# tests/integration/__init__.py
"""Integration tests for AI Beast workflows."""

# tests/integration/conftest.py
"""Shared fixtures for integration tests."""
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace with structure."""
    workspace = tmp_path / "ai_beast_test"
    workspace.mkdir()

    # Create directory structure
    for dir_name in ["config", "models", "data", "cache", "bin"]:
        (workspace / dir_name).mkdir()

    # Create mock beast CLI
    beast = workspace / "bin" / "beast"
    beast.write_text("#!/bin/bash\necho 'mock beast'")
    beast.chmod(0o755)

    return workspace


# tests/integration/test_model_workflow.py
"""Test complete model management workflow."""
import pytest
from modules.llm import LLMManager, ModelLocation

@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_download_workflow(temp_workspace):
    """Test: Complete model download, verify, use workflow."""
    manager = LLMManager(base_dir=temp_workspace)

    # Step 1: List available models
    available = manager.list_available_ollama_models()
    assert len(available) > 0

    # Step 2: Check storage before
    storage_before = manager.get_storage_info()
    assert "internal" in storage_before

    # Step 3: Download model (mock)
    # In real test, use a small test model or mock

    # Step 4: Verify it appears in list
    models = manager.list_all_models(force_scan=True)
    # ... assertions ...

    # Step 5: Check storage after
    storage_after = manager.get_storage_info()
    # ... verify storage changed ...


# tests/integration/test_rag_workflow.py
"""Test RAG ingestion workflow."""
import pytest
from modules.rag.ingest import ingest_directory

@pytest.mark.integration
def test_rag_ingestion_workflow(temp_workspace):
    """Test: Complete RAG ingestion workflow."""
    # Create test documents
    docs_dir = temp_workspace / "docs"
    docs_dir.mkdir()

    (docs_dir / "test1.md").write_text("# Test Document\n\nThis is content.")
    (docs_dir / "test2.txt").write_text("Another document with text.")

    # Ingest (dry-run first)
    result = ingest_directory(
        directory=docs_dir,
        collection="test_collection",
        apply=False
    )

    assert result["ok"]
    assert result["dryrun"]
    assert result["files"] == 2

    # Then real ingest (if Qdrant available)
    # ...


# tests/integration/test_agent_workflow.py
"""Test agent execution workflow."""
import pytest
from modules.agent import AgentOrchestrator

@pytest.mark.integration
def test_agent_task_execution(temp_workspace):
    """Test: Agent executes task and saves state."""
    orchestrator = AgentOrchestrator(
        base_dir=temp_workspace,
        apply=False
    )

    # Load initial state
    initial_state = orchestrator.load_state()
    assert initial_state.status == "idle"

    # Run task
    state = orchestrator.run_task(
        task="List files in config directory",
        max_steps=5
    )

    # Verify state updated
    assert state.status in ("completed", "failed")
    assert state.task_count == 1

    # Verify state persisted
    loaded_state = orchestrator.load_state()
    assert loaded_state.task_count == state.task_count
```

**Run integration tests:**
```bash
# Run only integration tests
python3 -m pytest tests/integration/ -v -m integration

# Skip integration tests in normal runs
python3 -m pytest -v -m "not integration"
```

**Related Files:**
- tests/integration/ (new directory)
- tests/integration/conftest.py (new)
- tests/integration/test_model_workflow.py (new)
- tests/integration/test_rag_workflow.py (new)
- tests/integration/test_agent_workflow.py (new)
- pytest.ini or pyproject.toml (add markers)

---

### Task 2.4: Add Benchmark Suite [P1, M]
**New Directory:** `tests/benchmarks/`

```python
# tests/benchmarks/__init__.py
"""Performance benchmarks for AI Beast."""

# tests/benchmarks/test_perf.py
"""Performance benchmarks using pytest-benchmark."""
import pytest
from modules.rag.ingest import chunk_text, embed_text
from modules.llm.manager import LLMManager

@pytest.mark.benchmark
def test_chunk_text_performance(benchmark):
    """Benchmark: Text chunking speed."""
    text = "word " * 10000  # 10k words

    result = benchmark(chunk_text, text, 1200, 200)

    # Assertions
    assert len(result) > 0
    # Should complete in < 100ms for 10k words
    assert benchmark.stats['mean'] < 0.1


@pytest.mark.benchmark
@pytest.mark.slow
def test_embedding_performance(benchmark):
    """Benchmark: Embedding generation speed."""
    chunks = ["test sentence " * 20 for _ in range(100)]

    # Skip if sentence-transformers not available
    pytest.importorskip("sentence_transformers")

    result = benchmark(embed_text, chunks)

    assert len(result) == 100
    # Should complete in < 5 seconds for 100 chunks
    assert benchmark.stats['mean'] < 5.0


@pytest.mark.benchmark
def test_model_scan_performance(benchmark, tmp_path):
    """Benchmark: Model directory scanning speed."""
    # Create mock model files
    models_dir = tmp_path / "models" / "llm"
    models_dir.mkdir(parents=True)

    for i in range(50):
        (models_dir / f"model_{i}.gguf").write_text("mock")

    manager = LLMManager(base_dir=tmp_path)

    result = benchmark(manager.scan_local_models, force=True)

    assert len(result) == 50
    # Should complete in < 500ms for 50 files
    assert benchmark.stats['mean'] < 0.5
```

**Run benchmarks:**
```bash
# Install benchmark plugin
pip install pytest-benchmark

# Run benchmarks
python3 -m pytest tests/benchmarks/ --benchmark-only -v

# Generate HTML report
python3 -m pytest tests/benchmarks/ --benchmark-only --benchmark-autosave --benchmark-save-data

# Compare benchmarks over time
python3 -m pytest tests/benchmarks/ --benchmark-compare
```

**Related Files:**
- tests/benchmarks/ (new directory)
- tests/benchmarks/test_perf.py (new)
- requirements-dev.txt (add pytest-benchmark)

---

### Task 2.5: Increase Test Coverage to 60%+ [P1, XL]
**Current:** <10% coverage
**Target:** 60%+ coverage

**Coverage report:**
```bash
# Install coverage tools
pip install pytest-cov

# Run with coverage
python3 -m pytest --cov=modules --cov=apps --cov=beast --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

**Priority modules to cover:**
1. modules/llm/manager.py (537 lines) - Target 70% coverage
2. modules/rag/ingest.py (401 lines) - Target 70% coverage
3. modules/evaluation/evaluator.py (519 lines) - Target 80% coverage
4. modules/agent/__init__.py (189 lines) - Target 75% coverage
5. modules/agent/agent_runner.py (190 lines) - Target 75% coverage
6. beast/cli.py (273 lines) - Target 60% coverage
7. beast/runtime.py (75 lines) - Target 90% coverage

**Example - Add tests for modules/llm/manager.py:**
```python
# tests/test_llm_manager.py
"""Comprehensive tests for LLM Manager."""
import pytest
from pathlib import Path
from modules.llm.manager import LLMManager, ModelLocation, ModelInfo, _human_size, _extract_quant

class TestHumanSize:
    """Test _human_size helper function."""

    def test_bytes(self):
        assert _human_size(100) == "100.0 B"

    def test_kilobytes(self):
        assert _human_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert _human_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert _human_size(5 * 1024 * 1024 * 1024) == "5.0 GB"


class TestExtractQuant:
    """Test _extract_quant helper function."""

    def test_q4_k_m(self):
        assert _extract_quant("model-Q4_K_M.gguf") == "Q4_K_M"

    def test_q8_0(self):
        assert _extract_quant("llama-2-7b-Q8_0.gguf") == "Q8_0"

    def test_fp16(self):
        assert _extract_quant("model-fp16.safetensors") == "FP16"

    def test_no_quant(self):
        assert _extract_quant("model.gguf") == ""


class TestLLMManager:
    """Test LLMManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        return LLMManager(base_dir=tmp_path)

    def test_initialization(self, manager, tmp_path):
        """Test manager initializes correctly."""
        assert manager.base_dir == tmp_path
        assert manager.models_dir.exists()
        assert manager.llm_models_dir.exists()
        assert manager.llm_cache_dir.exists()

    def test_scan_local_models_empty(self, manager):
        """Test scanning empty directory."""
        models = manager.scan_local_models(force=True)
        assert models == []

    def test_scan_local_models_with_files(self, manager, tmp_path):
        """Test scanning directory with model files."""
        # Create mock model files
        models_dir = tmp_path / "models" / "llm"
        models_dir.mkdir(parents=True)

        (models_dir / "model1.gguf").write_text("mock")
        (models_dir / "model2.safetensors").write_text("mock")
        (models_dir / "not_a_model.txt").write_text("mock")

        models = manager.scan_local_models(force=True)

        assert len(models) == 2
        assert all(isinstance(m, ModelInfo) for m in models)
        assert {m.name for m in models} == {"model1", "model2"}

    def test_cache_ttl(self, manager, tmp_path):
        """Test cache TTL mechanism."""
        models_dir = tmp_path / "models" / "llm"
        models_dir.mkdir(parents=True)
        (models_dir / "model.gguf").write_text("mock")

        # First scan
        models1 = manager.scan_local_models(force=False)

        # Second scan (should use cache)
        models2 = manager.scan_local_models(force=False)

        # Should be same
        assert len(models1) == len(models2)

        # Force scan should refresh
        models3 = manager.scan_local_models(force=True)
        assert len(models3) == len(models1)

    def test_storage_info(self, manager, tmp_path):
        """Test storage info retrieval."""
        info = manager.get_storage_info()

        assert "internal" in info
        assert "models_root" in info
        assert info["internal"]["path"] == str(tmp_path / "models" / "llm")

    @pytest.mark.skipif(not shutil.which("docker"), reason="Docker not available")
    def test_ollama_running(self, manager):
        """Test Ollama connection check."""
        # This will fail if Ollama not running, but shouldn't crash
        result = manager.ollama_running()
        assert isinstance(result, bool)

# Add more test classes for:
# - TestModelDeletion
# - TestModelMoving
# - TestDownloadValidation
# etc.
```

**Tracking coverage:**
```bash
# Add to .github/workflows/ci.yml
- name: Run tests with coverage
  run: |
    python3 -m pytest --cov=. --cov-report=xml --cov-report=term

- name: Check coverage threshold
  run: |
    coverage report --fail-under=60
```

**Related Files:**
- tests/test_llm_manager.py (new, ~500 lines)
- tests/test_rag_comprehensive.py (new, ~300 lines)
- tests/test_agent_comprehensive.py (new, ~300 lines)
- tests/test_evaluation_comprehensive.py (new, ~200 lines)
- .github/workflows/ci.yml (update)

---

## PHASE 3: ARCHITECTURE IMPROVEMENTS (P1-P2)

### Task 3.1: Implement Dependency Injection Container [P1, L]
**New File:** `modules/container.py`

```python
"""Dependency injection container for AI Beast.

Provides centralized configuration and dependency management.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar('T')


@dataclass
class AppContext:
    """Application context with all configuration."""

    # Directories
    base_dir: Path
    guts_dir: Path
    heavy_dir: Path
    models_dir: Path
    data_dir: Path
    outputs_dir: Path
    cache_dir: Path
    backup_dir: Path
    log_dir: Path

    # Runtime settings
    apply_mode: bool = False
    verbose: bool = False
    dry_run: bool = True

    # Service URLs
    ollama_url: str = "http://127.0.0.1:11434"
    qdrant_url: str = "http://127.0.0.1:6333"

    # Ports
    ports: dict[str, int] = field(default_factory=dict)

    # Feature flags
    features: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> AppContext:
        """Load configuration from environment variables.

        Args:
            base_dir: Base directory (detected if not provided)

        Returns:
            AppContext instance
        """
        if base_dir is None:
            base_dir = cls._detect_base_dir()

        # Load paths
        paths = cls._load_paths_env(base_dir)

        # Load ports
        ports = cls._load_ports_env(base_dir)

        # Load features
        features = cls._load_features_env(base_dir)

        return cls(
            base_dir=base_dir,
            guts_dir=Path(paths.get("GUTS_DIR", str(base_dir))),
            heavy_dir=Path(paths.get("HEAVY_DIR", str(base_dir))),
            models_dir=Path(paths.get("MODELS_DIR", str(base_dir / "models"))),
            data_dir=Path(paths.get("DATA_DIR", str(base_dir / "data"))),
            outputs_dir=Path(paths.get("OUTPUTS_DIR", str(base_dir / "outputs"))),
            cache_dir=Path(paths.get("CACHE_DIR", str(base_dir / "cache"))),
            backup_dir=Path(paths.get("BACKUP_DIR", str(base_dir / "backups"))),
            log_dir=Path(paths.get("LOG_DIR", str(base_dir / "logs"))),
            ollama_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
            qdrant_url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333"),
            ports=ports,
            features=features,
        )

    @staticmethod
    def _detect_base_dir() -> Path:
        """Detect BASE_DIR from environment or filesystem."""
        if base := os.environ.get("BASE_DIR"):
            return Path(base)

        # Walk up from cwd to find project root
        cwd = Path.cwd()
        for path in [cwd] + list(cwd.parents):
            if (path / "bin" / "beast").exists():
                return path

        return cwd

    @staticmethod
    def _load_paths_env(base_dir: Path) -> dict[str, str]:
        """Load paths.env file."""
        paths_file = base_dir / "config" / "paths.env"
        if not paths_file.exists():
            return {}

        paths = {}
        for line in paths_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, value = line.split("=", 1)
                paths[key.strip()] = value.strip().strip('"').strip("'")

        return paths

    @staticmethod
    def _load_ports_env(base_dir: Path) -> dict[str, int]:
        """Load ports.env file."""
        ports_file = base_dir / "config" / "ports.env"
        if not ports_file.exists():
            return {}

        ports = {}
        for line in ports_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, value = line.split("=", 1)
                try:
                    ports[key.strip()] = int(value.strip().strip('"').strip("'"))
                except ValueError:
                    pass

        return ports

    @staticmethod
    def _load_features_env(base_dir: Path) -> dict[str, bool]:
        """Load features.env file."""
        features_file = base_dir / "config" / "features.env"
        if not features_file.exists():
            return {}

        features = {}
        for line in features_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, value = line.split("=", 1)
                value_str = value.strip().strip('"').strip("'")
                features[key.strip()] = value_str.lower() in ("1", "true", "yes")

        return features


class Container:
    """Dependency injection container.

    Usage:
        container = Container(context)
        llm_manager = container.get(LLMManager)
        rag_ingestor = container.get(RAGIngestor)
    """

    def __init__(self, context: AppContext):
        self.context = context
        self._singletons: dict[type, Any] = {}
        self._factories: dict[type, Callable] = {}

    def register(self, interface: type[T], factory: Callable[[], T]) -> None:
        """Register a factory for a type."""
        self._factories[interface] = factory

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """Register a singleton instance."""
        self._singletons[interface] = instance

    def get(self, interface: type[T]) -> T:
        """Get instance of a type."""
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]

        # Check factories
        if interface in self._factories:
            instance = self._factories[interface]()
            self._singletons[interface] = instance
            return instance

        raise ValueError(f"No factory registered for {interface}")

    def setup_defaults(self) -> None:
        """Setup default factories for common types."""
        from modules.llm import LLMManager
        from modules.rag.ingest import RAGIngestor
        from modules.agent import AgentOrchestrator
        from modules.evaluation import Evaluator

        self.register(
            LLMManager,
            lambda: LLMManager(base_dir=self.context.base_dir)
        )

        self.register(
            AgentOrchestrator,
            lambda: AgentOrchestrator(
                base_dir=self.context.base_dir,
                apply=self.context.apply_mode
            )
        )

        self.register(
            Evaluator,
            lambda: Evaluator(root_dir=self.context.base_dir)
        )


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get global container instance."""
    global _container
    if _container is None:
        context = AppContext.from_env()
        _container = Container(context)
        _container.setup_defaults()
    return _container


def reset_container() -> None:
    """Reset global container (for testing)."""
    global _container
    _container = None
```

**Update modules to use DI:**
```python
# modules/llm/manager.py
# BEFORE:
class LLMManager:
    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else self._detect_base_dir()
        self._load_paths()

# AFTER:
from modules.container import AppContext

class LLMManager:
    def __init__(self, context: AppContext):
        """Initialize LLM Manager with dependency injection.

        Args:
            context: Application context with configuration
        """
        self.context = context
        self.base_dir = context.base_dir
        self.models_dir = context.models_dir / "llm"
        self.heavy_dir = context.heavy_dir
        # No need for _load_paths() anymore
```

**Related Files:**
- modules/container.py (new, ~250 lines)
- modules/llm/manager.py (update)
- modules/agent/__init__.py (update)
- modules/rag/ingest.py (update)
- tests/test_container.py (new, ~150 lines)

---

### Task 3.2: Implement Structured Logging [P1, M]
**New File:** `modules/logging_config.py`

```python
"""Structured logging configuration for AI Beast.

Uses structlog for structured, context-rich logging.
"""

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Path | None = None,
) -> None:
    """Configure structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to output JSON format
        log_file: Optional file to log to
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr if not log_file else open(log_file, "a"),
        level=getattr(logging, level.upper()),
    )

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


# Usage example:
# from modules.logging_config import get_logger
#
# logger = get_logger(__name__)
#
# logger.info("model_downloaded",
#             model_name="llama-3.2-3b",
#             size_bytes=2_000_000_000,
#             duration_ms=45000,
#             location="internal")
```

**Update modules to use structured logging:**
```python
# modules/llm/manager.py
# BEFORE:
import logging
logger = logging.getLogger(__name__)

def download_from_url(self, url: str, ...) -> dict:
    logger.info(f"Downloading from {url}")
    # ... download ...
    logger.info(f"Download complete: {dest_path}")

# AFTER:
from modules.logging_config import get_logger

logger = get_logger(__name__)

def download_from_url(self, url: str, ...) -> dict:
    logger.info("download_started",
                url=url,
                destination=str(dest_path))

    start_time = time.time()
    # ... download ...
    duration_ms = (time.time() - start_time) * 1000

    logger.info("download_completed",
                url=url,
                path=str(dest_path),
                size_bytes=os.path.getsize(dest_path),
                duration_ms=duration_ms)
```

**Related Files:**
- modules/logging_config.py (new, ~100 lines)
- requirements.txt (add structlog>=23.1.0)
- modules/llm/manager.py (update)
- modules/rag/ingest.py (update)
- modules/agent/__init__.py (update)
- All other modules (gradual update)

---

### Task 3.3: Convert to Async/Await for I/O [P2, XL]
**New File:** `modules/llm/manager_async.py`

```python
"""Async version of LLM Manager for better performance."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Callable

import aiohttp
from modules.container import AppContext
from modules.llm.manager import ModelInfo, ModelLocation
from modules.logging_config import get_logger

logger = get_logger(__name__)


class AsyncLLMManager:
    """Async LLM Manager with non-blocking I/O."""

    def __init__(self, context: AppContext):
        self.context = context
        self.base_dir = context.base_dir
        self.models_dir = context.models_dir / "llm"
        self.heavy_dir = context.heavy_dir
        self._model_cache: dict[str, ModelInfo] = {}
        self._cache_time: float = 0
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def scan_local_models_async(self, force: bool = False) -> list[ModelInfo]:
        """Scan for local models asynchronously."""
        # Use asyncio.to_thread for file I/O
        return await asyncio.to_thread(self._scan_local_models_sync, force)

    def _scan_local_models_sync(self, force: bool) -> list[ModelInfo]:
        """Synchronous scan implementation."""
        # Same logic as current scan_local_models
        # ...
        pass

    async def download_from_url_async(
        self,
        url: str,
        filename: str | None = None,
        destination: ModelLocation = ModelLocation.INTERNAL,
        custom_path: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        """Download a model asynchronously.

        Args:
            url: URL to download from
            filename: Optional filename
            destination: Where to save
            custom_path: Custom path if destination is CUSTOM
            progress_callback: Progress callback

        Returns:
            Dict with 'ok', 'path', 'size_bytes' keys
        """
        if not self._session:
            self._session = aiohttp.ClientSession()

        logger.info("download_started", url=url)

        # Determine destination path
        if destination == ModelLocation.CUSTOM and custom_path:
            dest_dir = Path(custom_path)
        elif destination == ModelLocation.EXTERNAL:
            dest_dir = self.heavy_dir / "models" / "llm"
        else:
            dest_dir = self.models_dir

        dest_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            filename = url.split("/")[-1].split("?")[0] or f"model_{int(asyncio.get_event_loop().time())}.gguf"

        dest_path = dest_dir / filename
        temp_path = dest_dir / f".{filename}.part"

        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                if resp.status != 200:
                    return {"ok": False, "error": f"HTTP {resp.status}"}

                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(temp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback({
                                "downloaded": downloaded,
                                "total": total,
                                "percent": (downloaded / total * 100) if total else 0,
                            })

                # Move to final location
                await asyncio.to_thread(temp_path.rename, dest_path)

                logger.info("download_completed",
                           url=url,
                           path=str(dest_path),
                           size_bytes=downloaded)

                return {
                    "ok": True,
                    "path": str(dest_path),
                    "size_bytes": downloaded,
                }

        except Exception as e:
            logger.error("download_failed", url=url, error=str(e))
            if temp_path.exists():
                await asyncio.to_thread(temp_path.unlink)
            return {"ok": False, "error": str(e)}

    async def list_ollama_models_async(self) -> list[ModelInfo]:
        """List Ollama models asynchronously."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            async with self._session.get(
                f"{self.context.ollama_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                models = []

                for m in data.get("models", []):
                    info = ModelInfo(
                        name=m.get("name", "unknown"),
                        path=f"ollama:{m.get('name')}",
                        size_bytes=m.get("size", 0),
                        size_human=self._human_size(m.get("size", 0)),
                        location=ModelLocation.OLLAMA,
                        model_type="ollama",
                        metadata=m,
                    )
                    models.append(info)

                return models

        except Exception as e:
            logger.error("ollama_list_failed", error=str(e))
            return []

    async def pull_ollama_model_async(
        self,
        model_name: str,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        """Pull an Ollama model asynchronously."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        logger.info("ollama_pull_started", model=model_name)

        try:
            async with self._session.post(
                f"{self.context.ollama_url}/api/pull",
                json={"name": model_name, "stream": True},
                timeout=aiohttp.ClientTimeout(total=3600)
            ) as resp:
                if resp.status != 200:
                    return {"ok": False, "error": f"HTTP {resp.status}"}

                async for line in resp.content:
                    if line:
                        try:
                            data = json.loads(line.decode())
                            if progress_callback:
                                progress_callback(data)

                            if data.get("status") == "success":
                                logger.info("ollama_pull_completed", model=model_name)
                                return {"ok": True, "model": model_name}
                        except json.JSONDecodeError:
                            continue

                return {"ok": True, "model": model_name}

        except Exception as e:
            logger.error("ollama_pull_failed", model=model_name, error=str(e))
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convert bytes to human readable."""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


# Usage example:
# async def main():
#     context = AppContext.from_env()
#     async with AsyncLLMManager(context) as manager:
#         models = await manager.list_ollama_models_async()
#         result = await manager.download_from_url_async("https://example.com/model.gguf")
```

**Related Files:**
- modules/llm/manager_async.py (new, ~400 lines)
- requirements.txt (add aiohttp>=3.9.0)
- tests/test_llm_manager_async.py (new, ~200 lines)

---

## PHASE 4: WEBUI & DASHBOARD ENHANCEMENTS (P1-P2)

### Task 4.1: Complete Dashboard UI [P1, L]
**Directory:** `apps/dashboard/static/`
**Current:** Basic dashboard exists
**Target:** Full-featured web UI

**File Structure:**
```
apps/dashboard/static/
├── index.html (update)
├── css/
│   ├── main.css (new)
│   └── themes/
│       ├── dark.css (new)
│       └── light.css (new)
├── js/
│   ├── app.js (new)
│   ├── components/
│   │   ├── models.js (new)
│   │   ├── services.js (new)
│   │   ├── config.js (new)
│   │   └── metrics.js (new)
│   └── api.js (new)
└── assets/
    └── logo.svg (new)
```

**index.html:**
```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Beast Dashboard</title>
    <link rel="stylesheet" href="/css/main.css">
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <h1>🐺 AI Beast Dashboard</h1>
            <div class="header-actions">
                <button id="theme-toggle" class="btn btn-icon">🌙</button>
                <button id="refresh-all" class="btn btn-primary">Refresh</button>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="container">
        <!-- Status Bar -->
        <section class="status-bar">
            <div class="status-item">
                <span class="status-label">Ollama</span>
                <span id="ollama-status" class="status-value">Checking...</span>
            </div>
            <div class="status-item">
                <span class="status-label">Qdrant</span>
                <span id="qdrant-status" class="status-value">Checking...</span>
            </div>
            <div class="status-item">
                <span class="status-label">Services</span>
                <span id="services-status" class="status-value">0/0</span>
            </div>
        </section>

        <!-- Tabs -->
        <nav class="tabs">
            <button class="tab active" data-tab="overview">Overview</button>
            <button class="tab" data-tab="models">Models</button>
            <button class="tab" data-tab="services">Services</button>
            <button class="tab" data-tab="config">Configuration</button>
            <button class="tab" data-tab="logs">Logs</button>
        </nav>

        <!-- Tab Panels -->
        <div class="tab-content">
            <!-- Overview Tab -->
            <div id="overview-tab" class="tab-panel active">
                <div class="grid">
                    <!-- System Metrics -->
                    <div class="card">
                        <h3>System Metrics</h3>
                        <div id="metrics-container">
                            <div class="metric">
                                <span class="metric-label">Memory</span>
                                <div class="metric-bar">
                                    <div id="memory-bar" class="metric-fill" style="width: 0%"></div>
                                </div>
                                <span id="memory-text" class="metric-value">0 GB / 0 GB</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Disk</span>
                                <div class="metric-bar">
                                    <div id="disk-bar" class="metric-fill" style="width: 0%"></div>
                                </div>
                                <span id="disk-text" class="metric-value">0 GB / 0 GB</span>
                            </div>
                        </div>
                    </div>

                    <!-- Quick Actions -->
                    <div class="card">
                        <h3>Quick Actions</h3>
                        <div class="actions">
                            <button class="btn btn-success" onclick="beast.run('up')">Start Services</button>
                            <button class="btn btn-danger" onclick="beast.run('down')">Stop Services</button>
                            <button class="btn" onclick="beast.run('status')">Status</button>
                            <button class="btn" onclick="beast.run('doctor')">Doctor</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Models Tab -->
            <div id="models-tab" class="tab-panel">
                <div class="card">
                    <div class="card-header">
                        <h3>LLM Models</h3>
                        <div class="card-actions">
                            <button class="btn btn-primary" onclick="models.showDownloadDialog()">Download</button>
                            <button class="btn" onclick="models.refresh()">Refresh</button>
                        </div>
                    </div>

                    <div class="tabs-secondary">
                        <button class="tab active" data-subtab="local">Local Models</button>
                        <button class="tab" data-subtab="ollama">Ollama Models</button>
                        <button class="tab" data-subtab="available">Available</button>
                    </div>

                    <div id="models-list" class="list">
                        <!-- Populated by JS -->
                    </div>
                </div>
            </div>

            <!-- Services Tab -->
            <div id="services-tab" class="tab-panel">
                <div class="card">
                    <h3>Docker Services</h3>
                    <div id="services-list" class="list">
                        <!-- Populated by JS -->
                    </div>
                </div>
            </div>

            <!-- Config Tab -->
            <div id="config-tab" class="tab-panel">
                <div class="card">
                    <h3>Configuration</h3>
                    <form id="config-form">
                        <div class="form-group">
                            <label for="guts-dir">Guts Directory</label>
                            <input type="text" id="guts-dir" class="form-control" placeholder="/path/to/guts">
                        </div>
                        <div class="form-group">
                            <label for="heavy-dir">Heavy Directory</label>
                            <input type="text" id="heavy-dir" class="form-control" placeholder="/path/to/heavy">
                        </div>
                        <button type="submit" class="btn btn-primary">Save Configuration</button>
                    </form>
                </div>
            </div>

            <!-- Logs Tab -->
            <div id="logs-tab" class="tab-panel">
                <div class="card">
                    <div class="card-header">
                        <h3>System Logs</h3>
                        <div class="card-actions">
                            <button class="btn" onclick="logs.refresh()">Refresh</button>
                            <button class="btn" onclick="logs.clear()">Clear</button>
                        </div>
                    </div>
                    <pre id="logs-output" class="logs"></pre>
                </div>
            </div>
        </div>
    </main>

    <!-- Modals -->
    <div id="download-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Download Model</h3>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                <form id="download-form">
                    <div class="form-group">
                        <label for="download-url">URL</label>
                        <input type="url" id="download-url" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label for="download-filename">Filename (optional)</label>
                        <input type="text" id="download-filename" class="form-control">
                    </div>
                    <div class="form-group">
                        <label for="download-location">Location</label>
                        <select id="download-location" class="form-control">
                            <option value="internal">Internal</option>
                            <option value="external">External</option>
                            <option value="custom">Custom</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary">Start Download</button>
                </form>
                <div id="download-progress" class="hidden">
                    <div class="progress-bar">
                        <div id="download-progress-fill" class="progress-fill"></div>
                    </div>
                    <span id="download-progress-text">0%</span>
                </div>
            </div>
        </div>
    </div>

    <script src="/js/api.js"></script>
    <script src="/js/components/models.js"></script>
    <script src="/js/components/services.js"></script>
    <script src="/js/app.js"></script>
</body>
</html>
```

**js/api.js:**
```javascript
// API client for dashboard backend
class API {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.token = localStorage.getItem('beast_token') || '';
    }

    async request(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.token) {
            headers['X-Beast-Token'] = this.token;
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: 'Request failed' }));
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        return response.json();
    }

    // Health
    async health() {
        return this.request('/api/health');
    }

    // Config
    async getConfig() {
        return this.request('/api/config');
    }

    async updatePaths(gutsDir, heavyDir) {
        return this.request('/api/paths', {
            method: 'POST',
            body: JSON.stringify({ guts_dir: gutsDir, heavy_dir: heavyDir }),
        });
    }

    // Models
    async listModels(force = false) {
        return this.request(`/api/models?force=${force ? '1' : '0'}`);
    }

    async listAvailableModels() {
        return this.request('/api/models/available');
    }

    async pullModel(modelName) {
        return this.request('/api/models/pull', {
            method: 'POST',
            body: JSON.stringify({ model: modelName }),
        });
    }

    async deleteModel(path) {
        return this.request('/api/models/delete', {
            method: 'POST',
            body: JSON.stringify({ path }),
        });
    }

    async downloadModel(url, filename, destination, customPath) {
        return this.request('/api/models/download', {
            method: 'POST',
            body: JSON.stringify({ url, filename, destination, custom_path: customPath }),
        });
    }

    async getModelStorage() {
        return this.request('/api/models/storage');
    }

    async getDownloadStatus(downloadId) {
        return this.request(`/api/models/downloads?id=${downloadId || ''}`);
    }

    // Services
    async getServices() {
        return this.request('/api/services');
    }

    // Metrics
    async getMetrics() {
        return this.request('/api/metrics');
    }

    // Beast commands
    async runCommand(cmd) {
        return this.request(`/api/run?cmd=${encodeURIComponent(cmd)}`);
    }

    // Extensions
    async listExtensions() {
        return this.request('/api/extensions');
    }

    async installExtension(name) {
        return this.request('/api/extensions/install', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    async toggleExtension(name, enable) {
        return this.request('/api/toggle', {
            method: 'POST',
            body: JSON.stringify({ kind: 'extension', name, enable }),
        });
    }

    // Packs
    async listPacks() {
        return this.request('/api/packs');
    }

    async togglePack(name, enable) {
        return this.request('/api/toggle', {
            method: 'POST',
            body: JSON.stringify({ kind: 'pack', name, enable }),
        });
    }
}

const api = new API();
```

**js/app.js:**
```javascript
// Main application logic
class App {
    constructor() {
        this.api = new API();
        this.currentTab = 'overview';
        this.autoRefreshInterval = null;
        this.init();
    }

    async init() {
        this.setupTabs();
        this.setupTheme();
        this.setupEventListeners();
        await this.loadInitialData();
        this.startAutoRefresh();
    }

    setupTabs() {
        document.querySelectorAll('.tab[data-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });
    }

    switchTab(tabName) {
        // Hide all tabs
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.remove('active');
        });

        // Show selected tab
        document.getElementById(`${tabName}-tab`).classList.add('active');
        document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');

        this.currentTab = tabName;
        this.loadTabData(tabName);
    }

    async loadTabData(tabName) {
        switch (tabName) {
            case 'overview':
                await this.loadOverview();
                break;
            case 'models':
                await models.loadModels();
                break;
            case 'services':
                await services.loadServices();
                break;
            case 'config':
                await this.loadConfig();
                break;
            case 'logs':
                await this.loadLogs();
                break;
        }
    }

    async loadInitialData() {
        try {
            await this.loadOverview();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    async loadOverview() {
        try {
            // Load metrics
            const { metrics } = await this.api.getMetrics();
            this.updateMetrics(metrics);

            // Load service status
            const models = await this.api.listModels();
            document.getElementById('ollama-status').textContent =
                models.ollama_running ? '✓ Running' : '✗ Stopped';

        } catch (error) {
            console.error('Failed to load overview:', error);
        }
    }

    updateMetrics(metrics) {
        const memory = metrics.memory || {};
        const memPercent = memory.percent_used || 0;
        document.getElementById('memory-bar').style.width = `${memPercent}%`;
        document.getElementById('memory-text').textContent =
            `${memory.used_gb || 0} GB / ${memory.total_gb || 0} GB`;

        const disk = metrics.disk_usage || {};
        const diskPercent = disk.percent_used || 0;
        document.getElementById('disk-bar').style.width = `${diskPercent}%`;
        document.getElementById('disk-text').textContent =
            `${disk.used_gb || 0} GB / ${disk.total_gb || 0} GB`;
    }

    async loadConfig() {
        try {
            const { config } = await this.api.getConfig();
            document.getElementById('guts-dir').value = config.GUTS_DIR || '';
            document.getElementById('heavy-dir').value = config.HEAVY_DIR || '';
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    async loadLogs() {
        // TODO: Implement log streaming
        document.getElementById('logs-output').textContent = 'Logs feature coming soon...';
    }

    setupTheme() {
        const theme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', theme);

        document.getElementById('theme-toggle').addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            const newTheme = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    setupEventListeners() {
        document.getElementById('refresh-all').addEventListener('click', () => {
            this.loadTabData(this.currentTab);
        });

        document.getElementById('config-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const gutsDir = document.getElementById('guts-dir').value;
            const heavyDir = document.getElementById('heavy-dir').value;

            try {
                await this.api.updatePaths(gutsDir, heavyDir);
                this.showSuccess('Configuration updated');
            } catch (error) {
                this.showError('Failed to update configuration');
            }
        });
    }

    startAutoRefresh() {
        this.autoRefreshInterval = setInterval(() => {
            if (this.currentTab === 'overview') {
                this.loadOverview();
            }
        }, 10000); // Refresh every 10 seconds
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type = 'info') {
        // TODO: Implement toast notifications
        console.log(`[${type}] ${message}`);
    }
}

// Beast command runner
const beast = {
    async run(cmd) {
        try {
            const result = await api.runCommand(cmd);
            console.log('Command result:', result);
            app.showSuccess(`Command ${cmd} completed`);
            app.loadTabData(app.currentTab);
        } catch (error) {
            console.error('Command failed:', error);
            app.showError(`Command ${cmd} failed`);
        }
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
```

**js/components/models.js:**
```javascript
// Model management component
const models = {
    currentModels: [],
    currentView: 'local',

    async loadModels() {
        try {
            const { models: modelList, ollama_running } = await api.listModels();
            this.currentModels = modelList;
            this.renderModels();
        } catch (error) {
            console.error('Failed to load models:', error);
            app.showError('Failed to load models');
        }
    },

    renderModels() {
        const container = document.getElementById('models-list');
        container.innerHTML = '';

        const filtered = this.currentModels.filter(m => {
            if (this.currentView === 'local') {
                return m.location !== 'ollama';
            } else if (this.currentView === 'ollama') {
                return m.location === 'ollama';
            }
            return true;
        });

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state">No models found</div>';
            return;
        }

        filtered.forEach(model => {
            const item = document.createElement('div');
            item.className = 'list-item';
            item.innerHTML = `
                <div class="list-item-content">
                    <div class="list-item-title">${model.name}</div>
                    <div class="list-item-meta">
                        <span class="badge">${model.location}</span>
                        <span>${model.size_human}</span>
                        ${model.quantization ? `<span class="badge badge-quant">${model.quantization}</span>` : ''}
                    </div>
                    <div class="list-item-path">${model.path}</div>
                </div>
                <div class="list-item-actions">
                    <button class="btn btn-sm btn-danger" onclick="models.deleteModel('${model.path}')">Delete</button>
                </div>
            `;
            container.appendChild(item);
        });
    },

    async deleteModel(path) {
        if (!confirm('Are you sure you want to delete this model?')) {
            return;
        }

        try {
            await api.deleteModel(path);
            app.showSuccess('Model deleted');
            await this.loadModels();
        } catch (error) {
            console.error('Failed to delete model:', error);
            app.showError('Failed to delete model');
        }
    },

    showDownloadDialog() {
        document.getElementById('download-modal').classList.add('show');
    },

    async refresh() {
        await this.loadModels();
    }
};

// Setup model tabs
document.querySelectorAll('.tabs-secondary .tab[data-subtab]').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tabs-secondary .tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        models.currentView = tab.dataset.subtab;
        models.renderModels();
    });
});
```

**css/main.css:**
```css
/* Main dashboard stylesheet */
:root {
    --primary: #3b82f6;
    --success: #10b981;
    --danger: #ef4444;
    --warning: #f59e0b;
    --background: #0f172a;
    --surface: #1e293b;
    --surface-hover: #334155;
    --text: #f1f5f9;
    --text-secondary: #94a3b8;
    --border: #334155;
}

[data-theme="light"] {
    --background: #f8fafc;
    --surface: #ffffff;
    --surface-hover: #f1f5f9;
    --text: #0f172a;
    --text-secondary: #64748b;
    --border: #e2e8f0;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--background);
    color: var(--text);
    line-height: 1.6;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 2rem;
}

/* Header */
.header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 0;
    position: sticky;
    top: 0;
    z-index: 100;
}

.header .container {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    font-size: 1.5rem;
    font-weight: 600;
}

.header-actions {
    display: flex;
    gap: 0.5rem;
}

/* Buttons */
.btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--surface);
    color: var(--text);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
}

.btn:hover {
    background: var(--surface-hover);
}

.btn-primary {
    background: var(--primary);
    color: white;
    border-color: var(--primary);
}

.btn-success {
    background: var(--success);
    color: white;
    border-color: var(--success);
}

.btn-danger {
    background: var(--danger);
    color: white;
    border-color: var(--danger);
}

.btn-sm {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
}

/* Cards */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.card h3 {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
}

/* Tabs */
.tabs {
    display: flex;
    gap: 0.5rem;
    border-bottom: 1px solid var(--border);
    margin: 2rem 0 1rem;
}

.tab {
    padding: 0.75rem 1.5rem;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
}

.tab:hover {
    color: var(--text);
}

.tab.active {
    color: var(--primary);
    border-bottom-color: var(--primary);
}

.tab-panel {
    display: none;
}

.tab-panel.active {
    display: block;
}

/* Grid */
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
}

/* Metrics */
.metric {
    margin-bottom: 1rem;
}

.metric-label {
    display: block;
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}

.metric-bar {
    height: 0.5rem;
    background: var(--surface-hover);
    border-radius: 0.25rem;
    overflow: hidden;
    margin-bottom: 0.25rem;
}

.metric-fill {
    height: 100%;
    background: var(--primary);
    transition: width 0.3s;
}

.metric-value {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

/* List */
.list-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    margin-bottom: 0.5rem;
    transition: all 0.2s;
}

.list-item:hover {
    background: var(--surface-hover);
}

.list-item-title {
    font-weight: 500;
    margin-bottom: 0.25rem;
}

.list-item-meta {
    display: flex;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.list-item-path {
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-family: 'Monaco', 'Courier New', monospace;
}

/* Badge */
.badge {
    padding: 0.125rem 0.5rem;
    border-radius: 0.25rem;
    background: var(--surface-hover);
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Forms */
.form-group {
    margin-bottom: 1rem;
}

.form-group label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 0.5rem;
}

.form-control {
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--background);
    color: var(--text);
    font-size: 0.875rem;
}

/* Status Bar */
.status-bar {
    display: flex;
    gap: 2rem;
    padding: 1rem 0;
    margin-bottom: 1rem;
}

.status-item {
    display: flex;
    flex-direction: column;
}

.status-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.status-value {
    font-size: 1rem;
    font-weight: 500;
    margin-top: 0.25rem;
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.8);
    z-index: 1000;
    align-items: center;
    justify-content: center;
}

.modal.show {
    display: flex;
}

.modal-content {
    background: var(--surface);
    border-radius: 0.5rem;
    max-width: 500px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--border);
}

.modal-body {
    padding: 1.5rem;
}

.modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: var(--text-secondary);
    cursor: pointer;
}

/* Progress Bar */
.progress-bar {
    height: 2rem;
    background: var(--surface-hover);
    border-radius: 0.5rem;
    overflow: hidden;
    margin-bottom: 0.5rem;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--success));
    transition: width 0.3s;
}

/* Logs */
.logs {
    background: var(--background);
    padding: 1rem;
    border-radius: 0.5rem;
    font-family: 'Monaco', 'Courier New', monospace;
    font-size: 0.75rem;
    line-height: 1.5;
    max-height: 500px;
    overflow-y: auto;
}

/* Utility Classes */
.hidden {
    display: none !important;
}

.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-secondary);
}
```

**Related Files:**
- apps/dashboard/static/index.html (update, ~500 lines)
- apps/dashboard/static/css/main.css (new, ~500 lines)
- apps/dashboard/static/js/api.js (new, ~150 lines)
- apps/dashboard/static/js/app.js (new, ~250 lines)
- apps/dashboard/static/js/components/models.js (new, ~100 lines)
- apps/dashboard/static/js/components/services.js (new, ~100 lines)

---

### Task 4.2: Add WebSocket Support for Real-time Updates [P2, M]
**File:** `apps/dashboard/dashboard.py`

```python
# Add WebSocket support using Quart
import asyncio
from quart import Quart, websocket
from quart_cors import cors

# Convert SimpleHTTPServer to Quart app
app = Quart(__name__, static_folder='static')
app = cors(app)

# Store connected WebSocket clients
connected_clients: set = set()


@app.route("/")
async def index():
    return await send_file(STATIC_DIR / "index.html")


@app.route("/api/health")
async def api_health():
    return {"ok": True, "base_dir": str(BASE_DIR)}


@app.websocket("/ws/updates")
async def ws_updates():
    """WebSocket endpoint for real-time updates."""
    connected_clients.add(websocket._get_current_object())

    try:
        while True:
            # Send periodic updates
            await asyncio.sleep(5)

            # Collect current status
            try:
                metrics = load_metrics()
                models_status = {
                    "ollama_running": get_llm_manager().ollama_running() if get_llm_manager() else False
                }

                await websocket.send_json({
                    "type": "update",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": {
                        "metrics": metrics,
                        "models": models_status,
                    }
                })
            except Exception as e:
                logger.error("websocket_update_failed", error=str(e))

    finally:
        connected_clients.discard(websocket._get_current_object())


async def broadcast_update(data: dict):
    """Broadcast update to all connected clients."""
    for client in connected_clients.copy():
        try:
            await client.send_json(data)
        except Exception:
            connected_clients.discard(client)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787)
```

**Client-side WebSocket:**
```javascript
// js/websocket.js
class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectDelay = 1000;
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected, reconnecting...');
                setTimeout(() => this.connect(), this.reconnectDelay);
                this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
            };
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
        }
    }

    handleMessage(data) {
        if (data.type === 'update' && window.app) {
            // Update metrics in UI
            window.app.updateMetrics(data.data.metrics);
        }
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
}

// Initialize WebSocket
const wsUrl = `ws://${window.location.host}/ws/updates`;
const ws = new WebSocketClient(wsUrl);
```

**Related Files:**
- apps/dashboard/dashboard.py (update to use Quart)
- apps/dashboard/static/js/websocket.js (new, ~100 lines)
- requirements.txt (add quart>=0.19.0, quart-cors>=0.7.0)

---

## PHASE 5: OLLAMA & WEBUI INTEGRATION (P1)

### Task 5.1: Deep Ollama Integration [P1, M]
**New File:** `modules/ollama/client.py`

```python
"""Enhanced Ollama client with full API support."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Callable

import aiohttp
from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)


class OllamaClient:
    """Enhanced Ollama API client."""

    def __init__(self, context: AppContext):
        self.context = context
        self.base_url = context.ollama_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        template: str | None = None,
        context: list[int] | None = None,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict | AsyncIterator[dict]:
        """Generate completion from a model.

        Args:
            model: Model name
            prompt: Prompt text
            system: System prompt
            template: Prompt template
            context: Context from previous response
            stream: Whether to stream response
            options: Model options (temperature, top_p, etc.)

        Returns:
            Response dict or async iterator of response chunks
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if system:
            payload["system"] = system
        if template:
            payload["template"] = template
        if context:
            payload["context"] = context
        if options:
            payload["options"] = options

        if stream:
            return self._stream_response("/api/generate", payload)
        else:
            return await self._request("/api/generate", payload)

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> dict | AsyncIterator[dict]:
        """Chat with a model.

        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream response
            options: Model options

        Returns:
            Response dict or async iterator of response chunks
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if options:
            payload["options"] = options

        if stream:
            return self._stream_response("/api/chat", payload)
        else:
            return await self._request("/api/chat", payload)

    async def embeddings(
        self,
        model: str,
        prompt: str | list[str],
    ) -> dict:
        """Generate embeddings.

        Args:
            model: Model name (e.g., "nomic-embed-text")
            prompt: Single prompt or list of prompts

        Returns:
            Dict with 'embedding' or 'embeddings' key
        """
        payload = {
            "model": model,
            "prompt": prompt,
        }

        return await self._request("/api/embeddings", payload)

    async def list_models(self) -> list[dict]:
        """List available models.

        Returns:
            List of model dicts
        """
        result = await self._request("/api/tags", method="GET")
        return result.get("models", [])

    async def show_model(self, name: str) -> dict:
        """Show model information.

        Args:
            name: Model name

        Returns:
            Model info dict
        """
        return await self._request("/api/show", {"name": name})

    async def pull_model(
        self,
        name: str,
        insecure: bool = False,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        """Pull a model from registry.

        Args:
            name: Model name
            insecure: Allow insecure connections
            progress_callback: Callback for progress updates

        Returns:
            Final status dict
        """
        payload = {
            "name": name,
            "insecure": insecure,
            "stream": True,
        }

        final_status = {}
        async for chunk in self._stream_response("/api/pull", payload):
            if progress_callback:
                progress_callback(chunk)
            final_status = chunk

        return final_status

    async def push_model(
        self,
        name: str,
        insecure: bool = False,
    ) -> dict:
        """Push a model to registry.

        Args:
            name: Model name
            insecure: Allow insecure connections

        Returns:
            Status dict
        """
        payload = {
            "name": name,
            "insecure": insecure,
            "stream": False,
        }

        return await self._request("/api/push", payload)

    async def create_model(
        self,
        name: str,
        modelfile: str,
        stream: bool = False,
    ) -> dict:
        """Create a model from a Modelfile.

        Args:
            name: Name for the new model
            modelfile: Modelfile contents
            stream: Whether to stream creation status

        Returns:
            Status dict
        """
        payload = {
            "name": name,
            "modelfile": modelfile,
            "stream": stream,
        }

        if stream:
            final_status = {}
            async for chunk in self._stream_response("/api/create", payload):
                final_status = chunk
            return final_status
        else:
            return await self._request("/api/create", payload)

    async def delete_model(self, name: str) -> dict:
        """Delete a model.

        Args:
            name: Model name

        Returns:
            Status dict
        """
        return await self._request("/api/delete", {"name": name}, method="DELETE")

    async def copy_model(self, source: str, destination: str) -> dict:
        """Copy a model.

        Args:
            source: Source model name
            destination: Destination model name

        Returns:
            Status dict
        """
        return await self._request("/api/copy", {"source": source, "destination": destination})

    async def _request(
        self,
        endpoint: str,
        data: dict | None = None,
        method: str = "POST",
    ) -> dict:
        """Make HTTP request to Ollama API.

        Args:
            endpoint: API endpoint
            data: Request data
            method: HTTP method

        Returns:
            Response dict
        """
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    return await resp.json()
            elif method == "DELETE":
                async with self._session.delete(url, json=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    return await resp.json() if resp.content_type == "application/json" else {"status": "success"}
            else:  # POST
                async with self._session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error("ollama_request_failed", endpoint=endpoint, error=str(e))
            raise

    async def _stream_response(
        self,
        endpoint: str,
        data: dict,
    ) -> AsyncIterator[dict]:
        """Stream response from Ollama API.

        Args:
            endpoint: API endpoint
            data: Request data

        Yields:
            Response chunks as dicts
        """
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}{endpoint}"

        async with self._session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
            async for line in resp.content:
                if line:
                    try:
                        yield json.loads(line.decode())
                    except json.JSONDecodeError:
                        continue


# Usage example:
# async def main():
#     context = AppContext.from_env()
#     async with OllamaClient(context) as client:
#         # Chat
#         messages = [
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user", "content": "Hello!"}
#         ]
#         response = await client.chat("llama3.2:latest", messages)
#         print(response["message"]["content"])
#
#         # Stream chat
#         async for chunk in await client.chat("llama3.2:latest", messages, stream=True):
#             print(chunk["message"]["content"], end="", flush=True)
```

**Related Files:**
- modules/ollama/client.py (new, ~400 lines)
- modules/ollama/__init__.py (new)
- tests/test_ollama_client.py (new, ~200 lines)

---

### Task 5.2: Open WebUI Integration & Configuration [P1, M]
**File:** `extensions/open_webui/config.yml`

```yaml
# Open WebUI Configuration
name: open_webui
description: ChatGPT-style interface for Ollama
version: "0.1.0"

# Service configuration
service:
  enabled: true
  image: ghcr.io/open-webui/open-webui:main
  container_name: ai_beast_open_webui

  # Port mapping
  ports:
    - "${AI_BEAST_BIND_ADDR:-127.0.0.1}:${PORT_WEBUI:-3000}:8080"

  # Environment variables
  environment:
    # Ollama connection
    OLLAMA_BASE_URL: "http://host.docker.internal:${PORT_OLLAMA:-11434}"

    # Qdrant for RAG
    QDRANT_URL: "http://qdrant:6333"

    # Authentication (disabled for local use)
    WEBUI_AUTH: "false"

    # RAG Features
    ENABLE_RAG_WEB_SEARCH: "true"
    RAG_EMBEDDING_MODEL: "nomic-embed-text"
    RAG_TOP_K: "5"

    # Model Settings
    DEFAULT_MODELS: "llama3.2:latest"
    MODEL_FILTER_ENABLED: "false"

    # File Upload
    ENABLE_IMAGE_GENERATION: "true"
    ENABLE_COMMUNITY_SHARING: "false"

    # Admin
    WEBUI_NAME: "AI Beast Chat"
    DEFAULT_USER_ROLE: "user"

  # Volumes
  volumes:
    - open_webui_data:/app/backend/data
    - ${MODELS_DIR:-./models}:/models:ro

  # Dependencies
  depends_on:
    qdrant:
      condition: service_healthy
      required: false

  # Network
  extra_hosts:
    - "host.docker.internal:host-gateway"

  # Health check
  healthcheck:
        # Note: 8080 here is the container-internal port for the Open WebUI image.
        test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s

# Integration scripts
scripts:
  post_install:
    - name: "Configure Open WebUI"
      command: "./scripts/configure_open_webui.sh"

    - name: "Import default models"
      command: "./scripts/import_webui_models.sh"

# Custom configuration files
files:
  - source: "config/webui_settings.json"
    destination: "/app/backend/data/config.json"
    template: true

# Documentation
docs:
  url: "https://github.com/open-webui/open-webui"
  notes: |
    Open WebUI provides a ChatGPT-like interface for Ollama.

    Features:
    - Chat with multiple models
    - RAG with document upload
    - Web search integration
    - Model management
    - User authentication (optional)

    Access at: http://localhost:${PORT_WEBUI:-3000}
```

**Configuration Script:**
```bash
#!/usr/bin/env bash
# scripts/configure_open_webui.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

info "Configuring Open WebUI..."

# Wait for service to be ready
info "Waiting for Open WebUI to be ready..."
for i in {1..30}; do
    if curl -sf "http://localhost:${PORT_WEBUI:-3000}/health" >/dev/null; then
        info "Open WebUI is ready"
        break
    fi
    sleep 2
done

# Configure default settings via API
info "Setting default configuration..."

# Set default model
curl -X POST "http://localhost:${PORT_WEBUI:-3000}/api/config" \
    -H "Content-Type: application/json" \
    -d '{
        "default_models": ["llama3.2:latest"],
        "rag_enabled": true,
        "web_search_enabled": true
    }' || warn "Failed to set config (may require authentication)"

info "Open WebUI configuration complete"
info "Access at: http://localhost:${PORT_WEBUI:-3000}"
```

**Related Files:**
- extensions/open_webui/config.yml (new, ~150 lines)
- extensions/open_webui/compose.fragment.yaml (update)
- scripts/configure_open_webui.sh (new, ~50 lines)
- scripts/import_webui_models.sh (new, ~50 lines)

---

Due to length constraints, I'll create a summary document of remaining tasks:

**Related Files:**
- IMPLEMENTATION_TASKS.md (this file, comprehensive task list)
- IMPLEMENTATION_TASKS_PART2.md (continuation with remaining phases)

The document continues with:
- Phase 6: Additional Extensions & Integrations
- Phase 7: Advanced Features
- Phase 8: Performance & Optimization
- Phase 9: Documentation & Polish
- Phase 10: Production Readiness

Each phase contains 10-20 detailed tasks with file locations, code examples, testing procedures, and verification steps.

Would you like me to continue with the remaining phases in a second document?
