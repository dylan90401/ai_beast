from pathlib import Path

from modules.tools.registry import load_tools_config, run_tool, save_tool_config


def test_tools_config_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = load_tools_config()
    assert data["version"] == 1
    save_tool_config("demo", {"name": "demo", "entrypoint": "echo", "args": "hello"})
    data = load_tools_config()
    assert "demo" in data["tools"]


def test_run_tool_missing(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, obj = run_tool("missing")
    assert code == 404
    assert obj["ok"] is False
