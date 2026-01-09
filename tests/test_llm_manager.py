"""Comprehensive tests for LLM Manager.

Task 2.5 - Increased test coverage for modules/llm/manager.py.
Target: 70% coverage.
"""
import shutil
from pathlib import Path

import pytest


# =============================================================================
# Test Helpers
# =============================================================================

class _ImmediateThread:
    """Mock thread that runs synchronously."""
    def __init__(self, target, daemon=False):
        self._target = target
        self.daemon = daemon

    def start(self):
        self._target()


class _DummyResp:
    """Mock HTTP response for download tests."""
    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0
        self.headers = {"Content-Length": str(len(data))}
        self.status = 200

    def read(self, size: int):
        if self._offset >= len(self._data):
            return b""
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHumanSize:
    """Test _human_size helper function."""

    def test_bytes(self):
        from modules.llm.manager import _human_size
        assert _human_size(100) == "100.0 B"

    def test_kilobytes(self):
        from modules.llm.manager import _human_size
        assert _human_size(1024) == "1.0 KB"

    def test_megabytes(self):
        from modules.llm.manager import _human_size
        result = _human_size(1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        from modules.llm.manager import _human_size
        result = _human_size(5 * 1024 * 1024 * 1024)
        assert "GB" in result

    def test_terabytes(self):
        from modules.llm.manager import _human_size
        result = _human_size(2 * 1024 * 1024 * 1024 * 1024)
        assert "TB" in result

    def test_zero(self):
        from modules.llm.manager import _human_size
        assert _human_size(0) == "0.0 B"


class TestExtractQuant:
    """Test _extract_quant helper function."""

    def test_q4_k_m(self):
        from modules.llm.manager import _extract_quant
        assert _extract_quant("model-Q4_K_M.gguf") == "Q4_K_M"

    def test_q8_0(self):
        from modules.llm.manager import _extract_quant
        assert _extract_quant("llama-2-7b-Q8_0.gguf") == "Q8_0"

    def test_fp16(self):
        from modules.llm.manager import _extract_quant
        result = _extract_quant("model-fp16.safetensors")
        assert result == "FP16"

    def test_fp32(self):
        from modules.llm.manager import _extract_quant
        result = _extract_quant("model_fp32.bin")
        assert result == "FP32"

    def test_no_quant(self):
        from modules.llm.manager import _extract_quant
        assert _extract_quant("model.gguf") == ""

    def test_lowercase_quant(self):
        from modules.llm.manager import _extract_quant
        result = _extract_quant("model-q5_k_s.gguf")
        assert result == "Q5_K_S"


class TestValidateDownloadUrl:
    """Test URL validation function."""

    def test_empty_url(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("")
        assert not ok
        assert "required" in msg.lower()

    def test_invalid_scheme(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("ftp://example.com/x.gguf")
        assert not ok

    def test_localhost_blocked(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("http://localhost/model.gguf")
        assert not ok

    def test_127_blocked(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("http://127.0.0.1/model.gguf")
        assert not ok

    def test_valid_http(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("http://example.com/model.gguf")
        assert ok

    def test_valid_https(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("https://huggingface.co/model.gguf")
        assert ok

    def test_url_with_whitespace(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("https://example.com/model name.gguf")
        assert not ok

    def test_url_too_long(self):
        from modules.llm import manager
        long_url = "https://example.com/" + "a" * 3000
        ok, msg = manager._validate_download_url(long_url)
        assert not ok

    def test_url_with_credentials_rejected(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("https://user:pass@example.com/model.gguf")
        assert not ok
        assert "credentials" in msg.lower()

    def test_private_ip_literal_blocked(self):
        from modules.llm import manager
        ok, msg = manager._validate_download_url("http://192.168.1.10/model.gguf")
        assert not ok
        assert "private" in msg.lower() or "local" in msg.lower()


class TestSafeFilename:
    """Test filename sanitization."""

    def test_path_traversal(self):
        from modules.llm import manager
        assert manager._safe_filename("../evil") == ""

    def test_empty(self):
        from modules.llm import manager
        assert manager._safe_filename("") == ""

    def test_backslash(self):
        from modules.llm import manager
        assert manager._safe_filename("..\\evil") == ""

    def test_dot(self):
        from modules.llm import manager
        assert manager._safe_filename(".") == ""

    def test_dotdot(self):
        from modules.llm import manager
        assert manager._safe_filename("..") == ""

    def test_valid_filename(self):
        from modules.llm import manager
        assert manager._safe_filename("model.gguf") == "model.gguf"


class TestResolveDest:
    """Test destination path resolution."""

    def test_valid_path(self, tmp_path):
        from modules.llm import manager
        ok, dest = manager._resolve_dest(tmp_path, "model.gguf")
        assert ok
        assert isinstance(dest, Path)
        assert dest.name == "model.gguf"

    def test_traversal_blocked(self, tmp_path):
        from modules.llm import manager
        ok, result = manager._resolve_dest(tmp_path, "../../../etc/passwd")
        # Should either fail or stay within directory
        if ok:
            assert str(result).startswith(str(tmp_path))


# =============================================================================
# LLMManager Class Tests
# =============================================================================

class TestLLMManagerInit:
    """Test LLMManager initialization."""

    def test_with_base_dir(self, tmp_path):
        from modules.llm.manager import LLMManager
        
        # Create required directories
        (tmp_path / "config").mkdir()
        
        mgr = LLMManager(base_dir=tmp_path)
        assert mgr.base_dir == tmp_path

    def test_creates_directories(self, tmp_path):
        from modules.llm.manager import LLMManager
        
        mgr = LLMManager(base_dir=tmp_path)
        
        assert mgr.models_dir.exists()
        assert mgr.llm_models_dir.exists()
        assert mgr.llm_cache_dir.exists()

    def test_loads_paths_env(self, tmp_path):
        from modules.llm.manager import LLMManager
        
        # Create paths.env
        config = tmp_path / "config"
        config.mkdir()
        (config / "paths.env").write_text(f'''
MODELS_DIR="{tmp_path}/custom_models"
''')
        
        mgr = LLMManager(base_dir=tmp_path)
        assert "custom_models" in str(mgr.models_dir)


class TestLLMManagerScanning:
    """Test model scanning functionality."""

    @pytest.fixture
    def manager(self, tmp_path):
        from modules.llm.manager import LLMManager
        return LLMManager(base_dir=tmp_path)

    def test_scan_empty(self, manager):
        models = manager.scan_local_models(force=True)
        assert models == []

    def test_scan_with_gguf_files(self, manager, tmp_path):
        # Create mock model files
        models_dir = tmp_path / "models" / "llm"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        (models_dir / "model1.gguf").write_text("mock")
        (models_dir / "model2.gguf").write_text("mock")
        
        models = manager.scan_local_models(force=True)
        assert len(models) == 2

    def test_scan_ignores_non_model_files(self, manager, tmp_path):
        models_dir = tmp_path / "models" / "llm"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        (models_dir / "model.gguf").write_text("mock")
        (models_dir / "readme.txt").write_text("not a model")
        (models_dir / "config.json").write_text("{}")
        
        models = manager.scan_local_models(force=True)
        assert len(models) == 1

    def test_scan_cache(self, manager, tmp_path):
        models_dir = tmp_path / "models" / "llm"
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / "model.gguf").write_text("mock")
        
        # First scan
        models1 = manager.scan_local_models(force=True)
        
        # Second scan (cached)
        models2 = manager.scan_local_models(force=False)
        
        assert len(models1) == len(models2)


class TestLLMManagerDownload:
    """Test download functionality."""

    def test_download_success(self, tmp_path, monkeypatch):
        import threading
        import urllib.request
        from modules.llm.manager import LLMManager, ModelLocation

        base = tmp_path / "base"
        base.mkdir()
        mgr = LLMManager(base_dir=base)

        dummy = _DummyResp(b"model data")
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: dummy)
        monkeypatch.setattr(threading, "Thread", _ImmediateThread)

        result = mgr.download_from_url(
            "http://example.com/model.gguf",
            destination=ModelLocation.INTERNAL,
        )
        assert result["ok"]
        assert Path(result["path"]).exists()

    def test_download_status(self, tmp_path, monkeypatch):
        import threading
        import urllib.request
        from modules.llm.manager import LLMManager, ModelLocation

        base = tmp_path / "base"
        base.mkdir()
        mgr = LLMManager(base_dir=base)

        dummy = _DummyResp(b"data")
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: dummy)
        monkeypatch.setattr(threading, "Thread", _ImmediateThread)

        result = mgr.download_from_url(
            "http://example.com/model.gguf",
            destination=ModelLocation.INTERNAL,
        )
        
        status = mgr.get_download_status(result["download_id"])
        assert status["status"] == "complete"

    def test_download_invalid_extension(self, tmp_path):
        from modules.llm.manager import LLMManager

        base = tmp_path / "base"
        base.mkdir()
        mgr = LLMManager(base_dir=base)

        result = mgr.download_from_url("http://example.com/file.txt")
        assert not result["ok"]

    def test_download_custom_path_relative(self, tmp_path):
        from modules.llm.manager import LLMManager, ModelLocation

        base = tmp_path / "base"
        base.mkdir()
        mgr = LLMManager(base_dir=base)

        result = mgr.download_from_url(
            "http://example.com/model.gguf",
            destination=ModelLocation.CUSTOM,
            custom_path="relative/path",
        )
        assert not result["ok"]


class TestLLMManagerStorage:
    """Test storage info functionality."""

    def test_get_storage_info(self, tmp_path):
        from modules.llm.manager import LLMManager
        
        mgr = LLMManager(base_dir=tmp_path)
        info = mgr.get_storage_info()
        
        assert isinstance(info, dict)
        assert "internal" in info


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_to_dict(self):
        from modules.llm.manager import ModelInfo, ModelLocation
        
        info = ModelInfo(
            name="test-model",
            path="/path/to/model.gguf",
            size_bytes=1024,
            location=ModelLocation.INTERNAL,
            model_type="gguf",
            quantization="Q4_K_M"
        )
        
        d = info.to_dict()
        
        assert d["name"] == "test-model"
        assert d["size_bytes"] == 1024
        assert d["location"] == "internal"
        assert d["model_type"] == "gguf"
        assert d["quantization"] == "Q4_K_M"

    def test_default_values(self):
        from modules.llm.manager import ModelInfo
        
        info = ModelInfo(name="test", path="/path")
        
        assert info.size_bytes == 0
        assert info.quantization == ""
        assert info.metadata == {}
