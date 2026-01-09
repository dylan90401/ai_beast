"""Tests for modules.registry.catalog.

Focused on verifying the registry works with the SQLite connection pool.
"""

from __future__ import annotations

from pathlib import Path

from modules.registry.catalog import ModelFamily, ModelMetadata, ModelRegistry


def test_model_registry_register_and_get(tmp_path: Path) -> None:
    db_path = tmp_path / "models.db"
    reg = ModelRegistry(db_path=db_path)

    meta = ModelMetadata(
        id="test-model-1",
        name="Test Model",
        version="1.0",
        family=ModelFamily.OTHER,
        size_bytes=123,
        tags=["test"],
        languages=["en"],
    )

    assert reg.register(meta) is True

    loaded = reg.get("test-model-1")
    assert loaded is not None
    assert loaded.id == meta.id
    assert loaded.name == meta.name

    results = reg.search(query="Test", limit=10)
    assert any(r.id == meta.id for r in results)
