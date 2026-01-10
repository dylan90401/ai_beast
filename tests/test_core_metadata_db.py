from modules.core.metadata_db import MetadataDB


def test_metadata_db_records_events(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = MetadataDB(dsn=None)
    db.record_event("test", "unit", {"ok": True})
    rows = db.list_events(limit=10)
    assert rows
    assert rows[0]["source"] == "test"
