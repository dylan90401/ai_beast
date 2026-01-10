"""
Tool registry for AI Beast.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from modules.core.logging import get_logger
from modules.core.metadata_db import get_metadata_db

logger = get_logger(__name__)

CONFIG_PATH = Path("config/tools.json")


@dataclass
class ToolConfig:
    name: str
    runner: str = "local"
    description: str = ""
    entrypoint: str = ""
    args: str = ""
    cwd: str = ""
    env: dict[str, str] | None = None
    test_command: str = ""
    test_url: str = ""
    install_command: str = ""
    download_url: str = ""
    config_hint: str = ""
    workflow: str = ""
    category: str = ""

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
            "install_command": self.install_command,
            "download_url": self.download_url,
            "config_hint": self.config_hint,
            "workflow": self.workflow,
            "category": self.category,
        }


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[2]


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
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def extract_all_tools(base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    tools_dir = _tools_dir(base)
    items = []
    for archive in sorted(tools_dir.glob("*.tar.gz")):
        code, obj = extract_tool(archive.stem.replace(".tar", ""), base)
        items.append({**obj, "status": code})
    return 200, {"ok": True, "items": items}


def download_tool_archive(name: str, url: str, base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    name = (name or "").strip()
    url = (url or "").strip()
    if not name or "/" in name or "\\" in name:
        return 400, {"ok": False, "error": "invalid tool name"}
    if not url:
        return 400, {"ok": False, "error": "missing download url"}
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return 400, {"ok": False, "error": "unsupported url scheme"}
    tools_dir = _tools_dir(base)
    tools_dir.mkdir(parents=True, exist_ok=True)
    archive = tools_dir / f"{name}.tar.gz"
    max_bytes = 2 * 1024 * 1024 * 1024
    try:
        req = Request(url, headers={"User-Agent": "ai-beast-tool-fetch"})
        with urlopen(req, timeout=30) as resp, archive.open("wb") as f:
            total = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    archive.unlink(missing_ok=True)
                    return 400, {"ok": False, "error": "download too large (max 2GB)"}
                f.write(chunk)
        return 200, {"ok": True, "name": name, "path": str(archive), "bytes": archive.stat().st_size}
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def update_tool_config(name: str, updates: dict[str, Any], base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    name = (name or "").strip()
    if not name:
        return 400, {"ok": False, "error": "missing tool name"}
    data = load_tools_config(base)
    tools = data.setdefault("tools", {})
    existing = tools.get(name) or {"name": name}
    allowed = {
        "name",
        "runner",
        "description",
        "entrypoint",
        "args",
        "cwd",
        "env",
        "test_command",
        "test_url",
        "install_command",
        "download_url",
        "config_hint",
        "workflow",
        "category",
    }
    for key, value in (updates or {}).items():
        if key in allowed:
            existing[key] = value
    tools[name] = existing
    path = _config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return 200, {"ok": True, "tool": existing}


def list_tools(base: Path | None = None) -> list[dict[str, Any]]:
    base = base or _base_dir()
    cfg = load_tools_config(base).get("tools", {})
    items = []
    for name, tool in sorted(cfg.items()):
        items.append({"name": name, **tool, "available": tool_available(tool)})
    return items


def tool_manifest(base: Path | None = None) -> dict[str, Any]:
    base = base or _base_dir()
    return {
        "version": 1,
        "tools": list_tools(base),
    }


def _build_env(env: dict[str, str] | None) -> dict[str, str]:
    merged = os.environ.copy()
    if env:
        merged.update({str(k): str(v) for k, v in env.items()})
    return merged


def tool_available(tool: dict[str, Any] | ToolConfig) -> bool:
    if isinstance(tool, ToolConfig):
        cmd = tool.entrypoint or tool.name
    else:
        cmd = tool.get("entrypoint") or tool.get("name") or ""
    if not cmd:
        return False
    exe = shlex.split(cmd)[0]
    return shutil.which(exe) is not None


def run_tool(
    name: str,
    mode: str = "run",
    entrypoint: str | None = None,
    args: str | None = None,
    base: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    cfg = load_tools_config(base).get("tools", {}).get(name)
    if not cfg:
        return 404, {"ok": False, "error": "tool not found"}
    tool = ToolConfig(**cfg)
    cmd = entrypoint or tool.entrypoint or tool.name
    if not cmd:
        return 400, {"ok": False, "error": "missing entrypoint"}
    extra = args if args is not None else tool.args
    cmd_parts = shlex.split(cmd) + (shlex.split(extra) if extra else [])
    try:
        p = subprocess.run(
            cmd_parts,
            cwd=tool.cwd or None,
            env=_build_env(tool.env),
            text=True,
            capture_output=True,
            check=False,
        )
        result = {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-20000:],
            "cmd": cmd_parts,
        }
        get_metadata_db().record_event("tool_run", name, {"mode": mode, "ok": result["ok"]})
        return 200, result
    except Exception as exc:
        logger.warning("Tool run failed", exc_info=exc)
        return 500, {"ok": False, "error": str(exc)}


def run_tool_test(name: str, base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    cfg = load_tools_config(base).get("tools", {}).get(name)
    if not cfg:
        return 404, {"ok": False, "error": "tool not found"}
    tool = ToolConfig(**cfg)
    if not tool.test_command and not tool.test_url:
        return 400, {"ok": False, "error": "missing test command/url"}
    if tool.test_url:
        return 200, {"ok": True, "test_url": tool.test_url}
    cmd_parts = shlex.split(tool.test_command)
    try:
        p = subprocess.run(
            cmd_parts,
            cwd=tool.cwd or None,
            env=_build_env(tool.env),
            text=True,
            capture_output=True,
            check=False,
        )
        result = {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-20000:],
            "cmd": cmd_parts,
        }
        get_metadata_db().record_event("tool_test", name, {"ok": result["ok"]})
        return 200, result
    except Exception as exc:
        logger.warning("Tool test failed", exc_info=exc)
        return 500, {"ok": False, "error": str(exc)}


def install_tool(name: str, run_installer: bool, base: Path | None = None) -> tuple[int, dict[str, Any]]:
    base = base or _base_dir()
    cfg = load_tools_config(base).get("tools", {}).get(name)
    if not cfg:
        return 404, {"ok": False, "error": "tool not found"}
    tool = ToolConfig(**cfg)
    if tool.install_command and run_installer:
        cmd_parts = shlex.split(tool.install_command)
        try:
            p = subprocess.run(
                cmd_parts,
                cwd=tool.cwd or None,
                env=_build_env(tool.env),
                text=True,
                capture_output=True,
                check=False,
            )
            return 200, {
                "ok": p.returncode == 0,
                "returncode": p.returncode,
                "stdout": p.stdout[-20000:],
                "stderr": p.stderr[-20000:],
                "cmd": cmd_parts,
            }
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}
    if tool.download_url:
        tools_dir = _tools_dir(base)
        archive = tools_dir / f"{name}.tar.gz"
        if not archive.exists():
            code, obj = download_tool_archive(name, tool.download_url, base)
            if code != 200:
                return code, obj
    else:
        tools_dir = _tools_dir(base)
        archive = tools_dir / f"{name}.tar.gz"
        if not archive.exists():
            return 400, {"ok": False, "error": "no installer configured (set download_url or install_command)"}
    code, obj = extract_tool(name, base)
    if code != 200:
        return code, obj
    return 200, {
        "ok": True,
        "name": name,
        "path": obj.get("path", ""),
        "installer": "skipped" if not run_installer else "not-configured",
    }
