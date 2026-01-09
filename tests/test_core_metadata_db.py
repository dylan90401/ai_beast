from modules.core.metadata_db import MetadataDB


def test_metadata_db_tool_runs(tmp_path):
    db = MetadataDB(f"sqlite://{tmp_path / 'meta.db'}")
    db.record_tool_run("nmap", True, returncode=0, duration_ms=12, meta={"args": "--version"})
    db.record_event("dashboard", "toggle", {"name": "qdrant"})
    rows = db.list_tool_runs()
    assert rows
    assert rows[0]["name"] == "nmap"
    assert rows[0]["ok"] is True
    events = db.list_events()
    assert events
    assert events[0]["category"] == "dashboard"
