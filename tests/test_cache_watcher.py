"""Tests for modules.cache.watcher.

These are integration-ish unit tests and will be skipped if `watchdog`
is not installed.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


def test_cache_manager_invalidates_on_file_change(tmp_path: Path) -> None:
    pytest.importorskip("watchdog")

    from modules.cache.watcher import CacheManager

    cm = CacheManager(auto_start=False)
    cache = cm.create_cache("models")
    cache["sentinel"] = 123

    cm.watch_directory(
        tmp_path,
        cache_key="models",
        patterns={"*.txt"},
        debounce_seconds=0.05,
    )

    cm.start()
    try:
        (tmp_path / "x.txt").write_text("hello", encoding="utf-8")

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if len(cache) == 0:
                break
            time.sleep(0.05)

        assert len(cache) == 0
    finally:
        cm.stop()
