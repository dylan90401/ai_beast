def test_list_capabilities_loads_defaults():
    from modules.capabilities.registry import list_capabilities

    caps = list_capabilities()
    ids = {c["id"] for c in caps}
    assert "text2image" in ids
    assert "rag_vector_db" in ids


def test_run_capability_checks_http(monkeypatch):
    from modules.capabilities.registry import run_capability_checks

    class DummyResp:
        status = 200

        def read(self):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: DummyResp())
    config = {"AI_BEAST_BIND_ADDR": "127.0.0.1", "PORT_COMFYUI": "8188"}
    results = run_capability_checks(config, capability_id="text2image")
    assert results
    assert all(r["ok"] for r in results)


def test_run_capability_checks_ollama_model(monkeypatch):
    from modules.capabilities.registry import run_capability_checks

    class DummyResp:
        status = 200

        def read(self):
            return b'{"models":[{"name":"llama3.2:latest"}]}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: DummyResp())
    config = {"AI_BEAST_BIND_ADDR": "127.0.0.1", "PORT_OLLAMA": "11434"}
    results = run_capability_checks(config, capability_id="ollama_chat")
    assert results
    assert all(r["ok"] for r in results)
