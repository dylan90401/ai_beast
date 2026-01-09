"""
Capability registry and validation helpers.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from modules.core.metadata_db import get_metadata_db
from modules.tools.registry import run_tool
from modules.utils import get_base_dir

CONFIG_PATH = Path("config/resources/capabilities.json")
LOCAL_PATH = Path("config/capabilities.local.json")


def _base_dir(base: Path | None = None) -> Path:
    return base or get_base_dir()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_capabilities(base: Path | None = None) -> dict[str, Any]:
    base_dir = _base_dir(base)
    data = _load_json(base_dir / CONFIG_PATH)
    local = _load_json(base_dir / LOCAL_PATH)
    caps = (data.get("capabilities") or {}).copy()
    for key, value in (local.get("capabilities") or {}).items():
        if not isinstance(value, dict):
            caps[key] = value
            continue
        base_cfg = dict(caps.get(key, {}) or {})
        local_cfg = dict(value)
        checks_append = local_cfg.pop("checks_append", None)
        actions_append = local_cfg.pop("actions_append", None)
        merged = {**base_cfg, **local_cfg}
        if checks_append:
            base_checks = list(merged.get("checks") or [])
            merged["checks"] = base_checks + list(checks_append)
        if actions_append:
            base_actions = list(merged.get("actions") or [])
            merged["actions"] = base_actions + list(actions_append)
        caps[key] = merged
    return {"version": data.get("version", 1), "capabilities": caps}


def list_capabilities(base: Path | None = None) -> list[dict[str, Any]]:
    data = load_capabilities(base)
    items = []
    for cid, cfg in sorted((data.get("capabilities") or {}).items()):
        item = {"id": cid, **cfg}
        items.append(item)
    return items


def _build_url(config: dict[str, str], port_key: str, path: str) -> str:
    port = config.get(port_key) or ""
    if not port:
        return ""
    bind = config.get("AI_BEAST_BIND_ADDR") or "127.0.0.1"
    suffix = f"/{path.lstrip('/')}" if path else ""
    return f"http://{bind}:{port}{suffix}"


def _http_check(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: int = 5,
) -> dict[str, Any]:
    if not url:
        return {"ok": False, "error": "missing url"}
    try:
        req_headers = {"User-Agent": "ai-beast-cap-check"}
        if headers:
            req_headers.update(headers)
        data = body.encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method.upper(), headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            return {"ok": 200 <= status < 400, "status": status}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _resolve_headers(check: dict[str, Any], config: dict[str, str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in (check.get("headers") or {}).items():
        if value is None:
            continue
        headers[str(key)] = str(value)
    for key, env_key in (check.get("headers_env") or {}).items():
        if not env_key:
            continue
        val = config.get(str(env_key)) or os.environ.get(str(env_key))
        if val:
            headers[str(key)] = str(val)
    return headers


def _resolve_body(check: dict[str, Any], config: dict[str, str]) -> str | None:
    if "body" in check:
        return str(check.get("body") or "")
    body_json = check.get("body_json")
    if body_json is not None:
        return json.dumps(body_json)
    env_key = check.get("body_env")
    if env_key:
        val = config.get(str(env_key)) or os.environ.get(str(env_key))
        if val is not None:
            return str(val)
    return None


def _tcp_check(port: int) -> dict[str, Any]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return {"ok": result == 0, "status": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _ollama_base(config: dict[str, str]) -> str:
    port = config.get("PORT_OLLAMA") or ""
    if not port:
        return ""
    bind = config.get("AI_BEAST_BIND_ADDR") or "127.0.0.1"
    return f"http://{bind}:{port}"


def _ollama_model_check(config: dict[str, str], model: str, timeout: int = 5) -> dict[str, Any]:
    model = (model or "").strip()
    if not model:
        return {"ok": False, "error": "missing model"}
    base = _ollama_base(config)
    if not base:
        return {"ok": False, "error": "missing ollama base"}
    url = f"{base}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-beast-cap-check"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        models = data.get("models") or []
        names = {str(item.get("name")) for item in models if isinstance(item, dict)}
        if model in names:
            return {"ok": True, "status": 200, "model": model, "url": url}
        return {"ok": False, "status": 200, "model": model, "url": url, "error": "model not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


def _compose_http_check(
    base: Path,
    service: str,
    port: int,
    path: str,
    compose_file: str | None = None,
) -> dict[str, Any]:
    if not service:
        return {"ok": False, "error": "missing service"}
    if port <= 0:
        return {"ok": False, "error": "missing port"}
    url = f"http://{service}:{port}/{path.lstrip('/')}" if path else f"http://{service}:{port}"
    compose = compose_file or str(base / "docker-compose.yml")
    cmd = ["docker", "compose", "-f", compose, "exec", "-T", service, "curl", "-fsS", url]
    p = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "ok": p.returncode == 0,
        "status": p.returncode,
        "stdout": (p.stdout or "")[-20000:],
        "stderr": (p.stderr or "")[-20000:],
        "url": url,
        "cmd": cmd,
    }


def run_capability_checks(
    config: dict[str, str],
    capability_id: str | None = None,
    allow_tool_runs: bool = False,
    base: Path | None = None,
) -> list[dict[str, Any]]:
    base_dir = _base_dir(base)
    caps = list_capabilities(base_dir)
    results: list[dict[str, Any]] = []
    for cap in caps:
        if capability_id and cap.get("id") != capability_id:
            continue
        checks = cap.get("checks") or []
        for check in checks:
            ctype = (check.get("type") or "http").lower()
            name = check.get("name") or cap.get("title") or cap.get("id")
            detail: dict[str, Any] = {"capability": cap.get("id"), "name": name, "type": ctype}
            if ctype == "http":
                url = _build_url(config, check.get("port", ""), check.get("path", ""))
                detail["url"] = url
                detail.update(
                    _http_check(
                        url,
                        method=str(check.get("method") or "GET"),
                        headers=_resolve_headers(check, config),
                        body=_resolve_body(check, config),
                        timeout=int(check.get("timeout", 5)),
                    )
                )
            elif ctype == "tcp":
                port_key = check.get("port", "")
                port_val = config.get(port_key)
                try:
                    port = int(port_val or 0)
                except ValueError:
                    port = 0
                detail["url"] = _build_url(config, port_key, "")
                if port <= 0:
                    detail.update({"ok": False, "error": "missing port"})
                else:
                    detail.update(_tcp_check(port))
            elif ctype == "tool":
                if not allow_tool_runs:
                    detail.update({"ok": False, "error": "tool runs require allow toggle"})
                else:
                    code, obj = run_tool(str(check.get("tool") or ""), mode="test", base=base_dir)
                    detail.update({"ok": obj.get("ok", False), "status": obj.get("returncode"), "stdout": obj.get("stdout", ""), "stderr": obj.get("stderr", ""), "code": code})
            elif ctype == "ollama_model":
                model = str(check.get("model") or "")
                detail.update(_ollama_model_check(config, model, timeout=int(check.get("timeout", 5))))
            elif ctype == "compose_http":
                if not allow_tool_runs:
                    detail.update({"ok": False, "error": "compose checks require allow toggle"})
                else:
                    port_key = check.get("port", "")
                    raw_port = check.get("service_port") or check.get("container_port")
                    if raw_port is None:
                        raw_port = config.get(port_key, "")
                    try:
                        port = int(raw_port or 0)
                    except ValueError:
                        port = 0
                    detail.update(
                        _compose_http_check(
                            base_dir,
                            str(check.get("service") or ""),
                            port,
                            str(check.get("path") or ""),
                            str(check.get("compose_file") or ""),
                        )
                    )
            else:
                detail.update({"ok": False, "error": f"Unsupported check type: {ctype}"})
            try:
                get_metadata_db().record_event(
                    "capability_check",
                    str(detail.get("name") or cap.get("id") or "check"),
                    {
                        "capability": cap.get("id"),
                        "type": ctype,
                        "ok": bool(detail.get("ok")),
                        "status": detail.get("status"),
                        "url": detail.get("url"),
                        "error": detail.get("error"),
                    },
                )
            except Exception:
                pass
            results.append(detail)
    return results
