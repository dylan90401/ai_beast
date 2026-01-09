"""
Tool registry for AI Beast.

Discovers tools in _ai_tools, merges per-tool config, and runs/tests tools.
"""

import json
import os
import shlex
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from modules.core.logging import get_logger
from modules.core.metadata_db import get_metadata_db
from modules.utils import get_base_dir

logger = get_logger(__name__)

CONFIG_PATH = "config/tools.json"


@dataclass
class ToolConfig:
    name: str
    runner: str = "local"
    description: str = ""
    entrypoint: str = ""
    args: str = ""
    cwd: str = ""
    env: dict[str, str] = None
    test_command: str = ""
    test_url: str = ""
    docker_image: str = ""
    docker_args: str = ""
    compose_service: str = ""
    compose_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runner": self.runner,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "args": self.args,
            "cwd": self.cwd,
            "env": self.env or {},
            "test_command": self.test_command,
            "test_url": self.test_url,
            "docker_image": self.docker_image,
            "docker_args": self.docker_args,
            "compose_service": self.compose_service,
            "compose_file": self.compose_file,
        }


def _base_dir() -> Path:
    return get_base_dir()


def _tools_dir(base: Path) -> Path:
    return base / "_ai_tools"


def _extract_dir(base: Path) -> Path:
    return _tools_dir(base) / "extracted"


def _config_path(base: Path) -> Path:
    return base / CONFIG_PATH


def load_tools_config(base: Path | None = None) -> dict[str, Any]:
    base = base or _base_dir()
    path = _config_path(base)
    if not path.exists():
        return {"version": 1, "tools": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "tools": {}}


def save_tool_config(name: str, config: dict[str, Any], base: Path | None = None) -> dict[str, Any]:
    base = base or _base_dir()
    path = _config_path(base)
    data = load_tools_config(base)
    tools = data.setdefault("tools", {})
    tools[name] = config
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data


def _safe_extract_tar(tar: tarfile.TarFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in tar.getmembers():
        member_path = dest / member.name
        if not str(member_path.resolve()).startswith(str(dest)):
            raise RuntimeError(f"Unsafe path in tar: {member.name}")
    tar.extractall(dest)


def _find_installer(root: Path) -> Path | None:
    for cand in ("install.sh", "setup.sh"):
        for p in root.rglob(cand):
            if p.is_file():
                return p
    return None


def _list_entrypoints(root: Path) -> list[str]:
    if not root.exists():
        return []
    entries: list[str] = []
    skip_dirs = {"__MACOSX", ".git", ".venv", "__pycache__", "node_modules"}
    max_depth = 4
    for p in root.rglob("*"):
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if any(part in skip_dirs for part in rel.parts):
            continue
        if len(rel.parts) > max_depth:
            continue
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if os.access(p, os.X_OK) or p.suffix.lower() in (".sh", ".py", ".pl", ".rb", ".js"):
            entries.append(str(rel))
        if len(entries) >= 24:
            break
    return sorted(entries)


def discover_archives(base: Path | None = None) -> list[dict[str, Any]]:
    base = base or _base_dir()
    tools_dir = _tools_dir(base)
    extract_dir = _extract_dir(base)
    if not tools_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(tools_dir.glob("*.tar.gz")):
        name = path.name[: -len(".tar.gz")]
        extract_path = extract_dir / name
        extracted = extract_path.exists()
        entrypoints = _list_entrypoints(extract_dir / name) if extracted else []
        has_installer = False
        try:
            with tarfile.open(path, "r:gz") as tf:
                for member in tf.getmembers():
                    base_name = Path(member.name).name.lower()
                    if base_name in ("install.sh", "setup.sh"):
                        has_installer = True
                        break
        except Exception:
            has_installer = False
        items.append(
            {
                "name": name,
                "archive": str(path),
                "size": str(path.stat().st_size),
                "mtime": str(int(path.stat().st_mtime)),
                "extracted": "true" if extracted else "false",
                "installer": "true" if has_installer else "false",
                "entrypoints": entrypoints,
                "path": str(extract_path) if extracted else "",
            }
        )
    return items


def extract_tool(name: str, base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    tools_dir = _tools_dir(base)
    extract_dir = _extract_dir(base)
    if not name or "/" in name or "\\" in name:
        return 400, {"ok": False, "error": "Invalid tool name"}
    archive = tools_dir / f"{name}.tar.gz"
    if not archive.exists():
        return 404, {"ok": False, "error": f"Tool archive not found: {name}"}
    target = extract_dir / name
    target.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tf:
            _safe_extract_tar(tf, target)
        return 200, {"ok": True, "name": name, "path": str(target)}
    except Exception as ex:
        return 500, {"ok": False, "error": str(ex)}


def install_tool(name: str, run_installer: bool, base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    code, obj = extract_tool(name, base)
    if code != 200:
        return code, obj
    target = Path(obj["path"])
    installer = _find_installer(target)
    if not run_installer:
        return 200, {"ok": True, "name": name, "path": str(target), "installer": str(installer) if installer else ""}
    if not installer:
        return 200, {"ok": True, "name": name, "path": str(target), "installer": "", "note": "No installer found"}
    try:
        p = subprocess.run(
            ["/bin/bash", str(installer)],
            cwd=str(installer.parent),
            text=True,
            capture_output=True,
            check=False,
        )
        return 200, {
            "ok": p.returncode == 0,
            "name": name,
            "path": str(target),
            "installer": str(installer),
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-20000:],
        }
    except Exception as ex:
        return 500, {"ok": False, "error": str(ex)}


def extract_all_tools(run_installer: bool = False, base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    tools = discover_archives(base)
    results = []
    for t in tools:
        name = t.get("name", "")
        if not name:
            continue
        code, obj = install_tool(name, run_installer, base)
        results.append(
            {
                "name": name,
                "ok": obj.get("ok", False),
                "error": obj.get("error", ""),
                "returncode": obj.get("returncode"),
            }
        )
    return 200, {"ok": True, "results": results, "run_installer": run_installer}


def _default_test_command(entrypoint: str) -> str:
    if not entrypoint:
        return ""
    return f"{entrypoint} --help"


def _merge_config(name: str, entrypoints: list[str], cfg: dict[str, Any], root_path: str) -> dict[str, Any]:
    entrypoint = cfg.get("entrypoint") or (entrypoints[0] if entrypoints else "")
    env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
    runner = str(cfg.get("runner") or "local")
    if runner not in ("local", "docker", "compose"):
        runner = "local"
    cwd = str(cfg.get("cwd") or "")
    if not cwd and root_path and runner == "local":
        cwd = root_path
    merged = ToolConfig(
        name=name,
        runner=runner,
        description=str(cfg.get("description") or ""),
        entrypoint=str(entrypoint or ""),
        args=str(cfg.get("args") or ""),
        cwd=cwd,
        env=env,
        test_command=str(cfg.get("test_command") or ""),
        test_url=str(cfg.get("test_url") or ""),
        docker_image=str(cfg.get("docker_image") or ""),
        docker_args=str(cfg.get("docker_args") or ""),
        compose_service=str(cfg.get("compose_service") or ""),
        compose_file=str(cfg.get("compose_file") or ""),
    )
    if not merged.test_command and not merged.test_url:
        merged.test_command = _default_test_command(merged.entrypoint)
    return merged.to_dict()


def list_tools(base: Path | None = None) -> list[dict[str, Any]]:
    base = base or _base_dir()
    archives = discover_archives(base)
    config = load_tools_config(base)
    cfg_tools = config.get("tools", {})
    items = []
    for tool in archives:
        name = tool["name"]
        merged = _merge_config(name, tool.get("entrypoints", []), cfg_tools.get(name, {}), tool.get("path", ""))
        items.append({**tool, "config": merged, "configured": name in cfg_tools})
    return items


def get_tool_config(name: str, base: Path | None = None) -> dict[str, Any]:
    base = base or _base_dir()
    tools = list_tools(base)
    for t in tools:
        if t["name"] == name:
            return t["config"]
    return _merge_config(name, [], {}, "")


def _env_pairs(env: dict[str, str]) -> list[str]:
    return [f"{k}={v}" for k, v in env.items() if k and v is not None]


def _build_local_command(entrypoint: str, args: str) -> list[str]:
    cmd = shlex.split(entrypoint) if entrypoint else []
    if args:
        cmd += shlex.split(args)
    return cmd


def _run_subprocess(cmd: list[str], cwd: Path | None, env: dict[str, str]) -> dict[str, Any]:
    merged_env = os.environ.copy()
    merged_env.update(env or {})
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "cmd": cmd,
        "stdout": (p.stdout or "")[-20000:],
        "stderr": (p.stderr or "")[-20000:],
    }


def _run_local(tool: dict[str, Any], base: Path, command: str) -> dict[str, Any]:
    entry = command or tool.get("entrypoint", "")
    args = tool.get("args", "")
    cwd = tool.get("cwd", "")
    cmd = _build_local_command(entry, args)
    if not cmd:
        return {"ok": False, "error": "Missing entrypoint"}
    resolved_cwd = Path(cwd).expanduser() if cwd else None
    if resolved_cwd and not resolved_cwd.is_absolute():
        resolved_cwd = base / resolved_cwd
    return _run_subprocess(cmd, resolved_cwd, tool.get("env", {}))


def _run_docker(tool: dict[str, Any], command: str) -> dict[str, Any]:
    image = tool.get("docker_image", "")
    if not image:
        return {"ok": False, "error": "Missing docker_image"}
    name = tool.get("name", "tool").replace("/", "_")
    docker_args = tool.get("docker_args", "")
    cmd = ["docker", "run", "--rm", "--name", f"ai_beast_tool_{name}"]
    for pair in _env_pairs(tool.get("env", {})):
        cmd += ["-e", pair]
    if docker_args:
        cmd += shlex.split(docker_args)
    entry = command or tool.get("entrypoint", "")
    if entry:
        cmd += [image] + shlex.split(entry)
    else:
        cmd += [image]
    if tool.get("args"):
        cmd += shlex.split(tool["args"])
    return _run_subprocess(cmd, None, {})


def _run_compose(tool: dict[str, Any], base: Path, command: str) -> dict[str, Any]:
    service = tool.get("compose_service", "")
    if not service:
        return {"ok": False, "error": "Missing compose_service"}
    compose_file = tool.get("compose_file") or str(base / "docker-compose.yml")
    cmd = ["docker", "compose", "-f", compose_file, "run", "--rm"]
    for pair in _env_pairs(tool.get("env", {})):
        cmd += ["-e", pair]
    cmd.append(service)
    entry = command or tool.get("entrypoint", "")
    if entry:
        cmd += shlex.split(entry)
    if tool.get("args"):
        cmd += shlex.split(tool["args"])
    return _run_subprocess(cmd, None, {})


def _tool_by_name(name: str, base: Path) -> dict[str, Any] | None:
    for t in list_tools(base):
        if t["name"] == name:
            return t
    return None


def run_tool(
    name: str,
    mode: str = "run",
    entrypoint: str | None = None,
    args: str | None = None,
    base: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    tool = _tool_by_name(name, base)
    if not tool:
        return 404, {"ok": False, "error": "Tool not found"}
    cfg = tool.get("config", {})
    tool_cfg = {**cfg}
    if entrypoint is not None:
        tool_cfg["entrypoint"] = entrypoint
    if args is not None:
        tool_cfg["args"] = args
    tool_cfg["name"] = name
    runner = tool_cfg.get("runner", "local")
    if mode == "test":
        test_url = tool_cfg.get("test_url", "")
        test_cmd = tool_cfg.get("test_command", "")
        if test_url:
            try:
                req = Request(test_url, headers={"User-Agent": "ai-beast-tool-test"})
                with urlopen(req, timeout=5) as resp:
                    status = resp.status
                    ok = 200 <= status < 400
                    return 200, {"ok": ok, "status": status, "url": test_url}
            except Exception as ex:
                return 200, {"ok": False, "error": str(ex), "url": test_url}
        if test_cmd:
            tool_cfg["entrypoint"] = test_cmd
            tool_cfg["args"] = ""
        else:
            return 400, {"ok": False, "error": "No test configured"}
    if runner == "docker":
        started = time.time()
        result = _run_docker(tool_cfg, tool_cfg.get("entrypoint", ""))
    elif runner == "compose":
        started = time.time()
        result = _run_compose(tool_cfg, base, tool_cfg.get("entrypoint", ""))
    else:
        started = time.time()
        result = _run_local(tool_cfg, base, tool_cfg.get("entrypoint", ""))
    try:
        duration_ms = int((time.time() - started) * 1000)
        db = get_metadata_db()
        db.record_tool_run(
            name,
            bool(result.get("ok")),
            returncode=result.get("returncode"),
            duration_ms=duration_ms,
            meta={"runner": runner, "mode": mode},
        )
    except Exception as exc:
        logger.warning("Failed to record tool run", exc_info=exc)
    return 200, result


def tool_manifest(base: Path | None = None) -> dict[str, Any]:
    base = base or _base_dir()
    tools = list_tools(base)
    manifest = []
    for t in tools:
        cfg = t.get("config", {})
        manifest.append(
            {
                "name": t["name"],
                "description": cfg.get("description", ""),
                "runner": cfg.get("runner", "local"),
                "entrypoint": cfg.get("entrypoint", ""),
                "args": cfg.get("args", ""),
                "test_command": cfg.get("test_command", ""),
                "test_url": cfg.get("test_url", ""),
            }
        )
    return {"ok": True, "tools": manifest}
