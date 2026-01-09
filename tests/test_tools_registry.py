import os
import tarfile
from pathlib import Path


def _write_tar_gz(archive: Path, root: Path) -> None:
    with tarfile.open(archive, "w:gz") as tf:
        for item in root.rglob("*"):
            tf.add(item, arcname=item.relative_to(root))


def test_registry_extract_and_config(tmp_path, monkeypatch):
    base = tmp_path / "base"
    tools_dir = base / "_ai_tools"
    tools_dir.mkdir(parents=True)
    monkeypatch.setenv("BASE_DIR", str(base))

    tool_root = tmp_path / "tool_src"
    tool_root.mkdir()
    (tool_root / "install.sh").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
    (tool_root / "tool.sh").write_text("#!/bin/bash\necho tool\n", encoding="utf-8")
    archive = tools_dir / "demo.tar.gz"
    _write_tar_gz(archive, tool_root)

    from modules.tools import registry

    code, extracted = registry.extract_tool("demo", base)
    assert code == 200
    assert extracted["ok"]
    assert Path(extracted["path"]).exists()

    code, info = registry.install_tool("demo", run_installer=False, base=base)
    assert code == 200
    assert info["ok"]
    assert "install.sh" in info["installer"]

    cfg = {
        "runner": "local",
        "description": "demo tool",
        "entrypoint": "tool.sh",
        "args": "",
    }
    data = registry.save_tool_config("demo", cfg, base)
    assert data["tools"]["demo"]["runner"] == "local"

    tools = registry.list_tools(base)
    assert any(t["name"] == "demo" for t in tools)
    tool = next(t for t in tools if t["name"] == "demo")
    assert tool["config"]["entrypoint"]


def test_registry_run_tool_local(tmp_path, monkeypatch):
    base = tmp_path / "base"
    tools_dir = base / "_ai_tools"
    tools_dir.mkdir(parents=True)
    monkeypatch.setenv("BASE_DIR", str(base))

    archive = tools_dir / "runner.tar.gz"
    with tarfile.open(archive, "w:gz"):
        pass

    from modules.tools import registry

    cfg = {
        "runner": "local",
        "entrypoint": os.environ.get("PYTHON", "python3"),
        "args": "-c \"print('ok')\"",
    }
    registry.save_tool_config("runner", cfg, base)

    code, result = registry.run_tool("runner", base=base)
    assert code == 200
    assert result["ok"]
    assert "ok" in result["stdout"]


def test_registry_rejects_invalid_name(tmp_path, monkeypatch):
    base = tmp_path / "base"
    (base / "_ai_tools").mkdir(parents=True)
    monkeypatch.setenv("BASE_DIR", str(base))

    from modules.tools import registry

    code, data = registry.extract_tool("bad/name", base)
    assert code == 400
    assert not data["ok"]
