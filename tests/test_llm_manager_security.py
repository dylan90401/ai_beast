from __future__ import annotations

from pathlib import Path

import pytest

from modules.llm.manager import LLMManager


def test_delete_local_model_allows_valid_model_file(tmp_path: Path):
    mgr = LLMManager(base_dir=tmp_path)

    model_dir = tmp_path / "models" / "llm"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_file = model_dir / "test-model.gguf"
    model_file.write_bytes(b"test")

    result = mgr.delete_local_model(str(model_file))
    assert result["ok"], result
    assert not model_file.exists()


def test_delete_local_model_blocks_symlink_attack(tmp_path: Path):
    mgr = LLMManager(base_dir=tmp_path)

    model_dir = tmp_path / "models" / "llm"
    model_dir.mkdir(parents=True, exist_ok=True)

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("secret")

    symlink = model_dir / "evil.gguf"
    symlink.symlink_to(secret_file)

    result = mgr.delete_local_model(str(symlink))
    assert not result["ok"], result
    assert "symlink" in result["error"].lower()

    assert secret_file.exists()
    assert symlink.exists()


@pytest.mark.parametrize(
    ("url", "should_allow"),
    [
        ("file:///etc/passwd", False),
        ("ftp://example.com/model.gguf", False),
        ("http://localhost:8080/model.gguf", False),
        ("http://127.0.0.1:8080/model.gguf", False),
        ("http://192.168.1.1/model.gguf", False),
        ("http://169.254.169.254/latest/meta-data", False),
        ("https://example.com/model.gguf", True),
    ],
)
def test_validate_download_url(url: str, should_allow: bool):
    ok, _err = LLMManager._validate_download_url(url)
    assert ok is should_allow
