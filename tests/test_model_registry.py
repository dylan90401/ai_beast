from modules.core.metadata_db import MetadataDB


def test_model_registry_register_and_rollback(tmp_path):
    db = MetadataDB(f"sqlite://{tmp_path / 'registry.db'}")
    res = db.register_model(
        name="llama3",
        version="v1",
        kind="ollama",
        path="/models/llama3.gguf",
    )
    assert res["ok"]
    models = db.list_models()
    assert models and models[0]["name"] == "llama3"
    versions = db.list_versions("llama3")
    assert versions and versions[0]["version"] == "v1"
    res2 = db.register_model(name="llama3", version="v2", kind="ollama")
    assert res2["ok"]
    roll = db.rollback_model("llama3", "v1")
    assert roll["ok"]
