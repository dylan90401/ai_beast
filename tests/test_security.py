"""Targeted security regression tests.

Focuses on path traversal / symlink escape and SSRF hardening.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.llm.manager import LLMManager


def test_delete_local_model_blocks_traversal_outside_model_dirs(tmp_path: Path) -> None:
    mgr = LLMManager(base_dir=tmp_path)

    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")

    models_llm = tmp_path / "models" / "llm"
    models_llm.mkdir(parents=True, exist_ok=True)

    # Attempt to escape models/llm -> base_dir
    escape_path = models_llm / ".." / ".." / "secret.txt"
    result = mgr.delete_local_model(str(escape_path))

    assert result["ok"] is False
    assert secret.exists() is True


def test_delete_local_model_symlink_target_escape_blocked(tmp_path: Path) -> None:
    mgr = LLMManager(base_dir=tmp_path)

    models_llm = tmp_path / "models" / "llm"
    models_llm.mkdir(parents=True, exist_ok=True)

    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")

    link = models_llm / "evil.gguf"
    link.symlink_to(secret)

    result = mgr.delete_local_model(str(link))
    assert result["ok"] is False
    assert secret.exists() is True


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1/model.gguf",
        "http://172.16.0.1/model.gguf",
        "http://192.168.0.1/model.gguf",
        "http://[::1]/model.gguf",
        "https://user:pass@example.com/model.gguf",
    ],
)
def test_validate_download_url_rejects_private_or_credentials(url: str) -> None:
    from modules.llm import manager

    ok, _ = manager._validate_download_url(url)
    assert ok is False
