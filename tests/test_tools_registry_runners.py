import tarfile
from pathlib import Path


def _empty_archive(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz"):
        pass


def test_run_tool_docker_builds_command(tmp_path, monkeypatch):
    from modules.tools import registry

    base = tmp_path / "base"
    tools_dir = base / "_ai_tools"
    archive = tools_dir / "dock.tar.gz"
    _empty_archive(archive)

    cfg = {
        "runner": "docker",
        "docker_image": "alpine:3.20",
        "entrypoint": "echo ok",
        "args": "",
    }
    registry.save_tool_config("dock", cfg, base)

    captured = {}

    def fake_run(cmd, cwd, env):
        captured["cmd"] = cmd
        return {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(registry, "_run_subprocess", fake_run)

    code, result = registry.run_tool("dock", base=base)
    assert code == 200
    assert result["ok"]
    assert captured["cmd"][:2] == ["docker", "run"]
    assert "alpine:3.20" in captured["cmd"]


def test_run_tool_compose_builds_command(tmp_path, monkeypatch):
    from modules.tools import registry

    base = tmp_path / "base"
    tools_dir = base / "_ai_tools"
    archive = tools_dir / "cmp.tar.gz"
    _empty_archive(archive)

    compose_file = base / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")

    cfg = {
        "runner": "compose",
        "compose_service": "svc",
        "compose_file": str(compose_file),
        "entrypoint": "echo ok",
        "args": "",
    }
    registry.save_tool_config("cmp", cfg, base)

    captured = {}

    def fake_run(cmd, cwd, env):
        captured["cmd"] = cmd
        return {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(registry, "_run_subprocess", fake_run)

    code, result = registry.run_tool("cmp", base=base)
    assert code == 200
    assert result["ok"]
    assert captured["cmd"][:3] == ["docker", "compose", "-f"]
    assert str(compose_file) in captured["cmd"]
    assert "svc" in captured["cmd"]
