from pathlib import Path

from modules.core.io import ensure_dir, read_json, write_json


def test_read_write_json(tmp_path: Path):
    target = tmp_path / "data" / "sample.json"
    payload = {"ok": True, "value": 42}
    write_json(target, payload)
    assert target.exists()
    assert read_json(target) == payload


def test_ensure_dir(tmp_path: Path):
    target = tmp_path / "nested" / "dir"
    ensure_dir(target)
    assert target.exists()
