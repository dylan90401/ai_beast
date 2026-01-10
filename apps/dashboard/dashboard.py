#!/usr/bin/env python3
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from modules.capabilities.registry import list_capabilities
from modules.llm.manager import LLMManager
from modules.tools.registry import (
    install_tool,
    list_tools,
    load_tools_config,
    run_tool,
    run_tool_test,
    update_tool_config,
)


def resolve_base_dir():
    bd = os.environ.get("BASE_DIR")
    if bd:
        return Path(bd)
    here = Path(__file__).resolve()
    # Walk upward until we find a project root indicator (beast dir, pyproject.toml, or .git)
    for p in [here] + list(here.parents):
        if (p / 'beast').exists() or (p / 'pyproject.toml').exists() or (p / '.git').exists():
            return p
    # Fallback for legacy layout
    return here.parents[2]


BASE_DIR = resolve_base_dir()
PATHS_ENV = BASE_DIR / "config" / "paths.env"
PORTS_ENV = BASE_DIR / "config" / "ports.env"
TOKEN_FILE = BASE_DIR / "config" / "secrets" / "dashboard_token.txt"
BEAST = BASE_DIR / "bin" / "beast"
STATIC_DIR = BASE_DIR / "apps" / "dashboard" / "static"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

ALLOW = {
    "init": ["init", "--apply"],
    "preflight": ["preflight"],
    "bootstrap_dry": ["bootstrap", "--dry-run"],
    "bootstrap_apply": ["bootstrap", "--apply"],
    "up": ["up"],
    "down": ["down"],
    "status": ["status"],
    "doctor": ["doctor"],
    "urls": ["urls"],
    "compose_gen": ["compose", "gen", "--apply"],
    "speech_up": ["speech", "up"],
    "speech_down": ["speech", "down"],
    "speech_status": ["speech", "status"],
}

# Cache for env config to avoid repeated subprocess calls
_env_cache = None
_env_cache_mtime = 0
_env_cache_ttl = 5.0  # seconds


def read_token():
    if not TOKEN_FILE.exists():
        return None
    t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t or None


def load_env_json():
    """Load environment config with caching to avoid repeated subprocess calls.

    Cache is invalidated after TTL or if config files are modified.
    """
    global _env_cache, _env_cache_mtime

    # Check if cache is valid
    current_time = time.time()
    cache_age = current_time - _env_cache_mtime

    # Get mtime of config files
    paths_mtime = PATHS_ENV.stat().st_mtime if PATHS_ENV.exists() else 0
    ports_mtime = PORTS_ENV.stat().st_mtime if PORTS_ENV.exists() else 0
    max_config_mtime = max(paths_mtime, ports_mtime)

    # Return cached value if still valid
    if _env_cache is not None and cache_age < _env_cache_ttl and max_config_mtime <= _env_cache_mtime:
        return _env_cache

    # Load fresh config
    script = f'''
set -euo pipefail
set -a
source "{PATHS_ENV}"
[ -f "{PORTS_ENV}" ] && source "{PORTS_ENV}" || true
set +a
python3 - <<'PY'
import os, json
keys=["BASE_DIR","GUTS_DIR","HEAVY_DIR","MODELS_DIR","DATA_DIR","OUTPUTS_DIR","CACHE_DIR","BACKUP_DIR","LOG_DIR","COMFYUI_DIR","VENV_DIR",
      "COMFYUI_MODELS_DIR","LLM_MODELS_DIR","LLM_CACHE_DIR","OLLAMA_MODELS","HF_HOME","TRANSFORMERS_CACHE",
      "HUGGINGFACE_HUB_CACHE","XDG_CACHE_HOME","TORCH_HOME",
      "PORT_WEBUI","PORT_COMFYUI","PORT_QDRANT","PORT_OLLAMA","PORT_DASHBOARD","PORT_N8N","PORT_KUMA","PORT_PORTAINER","PORT_JUPYTER",
      "PORT_LANGFLOW","PORT_FLOWISE","PORT_DIFY","PORT_TIKA","PORT_UNSTRUCTURED","PORT_OTEL_GRPC","PORT_OTEL_HTTP",
      "PORT_MINIO","PORT_MINIO_CONSOLE","PORT_SEARXNG","PORT_SPEECH_API","AI_BEAST_PROFILE","AI_BEAST_BIND_ADDR"]
print(json.dumps({{k: os.environ.get(k) for k in keys}}))
PY
'''
    out = subprocess.check_output(["/bin/bash", "-lc", script], text=True)
    result = json.loads(out)

    # Update cache
    _env_cache = result
    _env_cache_mtime = current_time

    return result


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def _sanitize_path(value: str, label: str) -> tuple[bool, str]:
    if not isinstance(value, str):
        return False, f"{label} must be a string"
    raw = value.strip()
    if not raw:
        return False, f"{label} cannot be empty"
    if "\n" in raw or "\r" in raw:
        return False, f"{label} cannot be multiline"
    if any(token in raw for token in ("Where should", "Enter path", "Default:")):
        return False, f"{label} looks like prompt text"
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return False, f"{label} must be an absolute path"
    return True, str(path)


def load_features_env() -> dict[str, str]:
    return read_env_file(BASE_DIR / "config" / "features.env")


def pack_flag_name(name: str) -> str:
    key = "".join([c if c.isalnum() else "_" for c in name]).upper()
    return f"FEATURE_PACKS_{key}"


def load_packs() -> dict:
    p = BASE_DIR / "config" / "packs.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def list_extensions() -> list[dict[str, str]]:
    exts = []
    root = BASE_DIR / "extensions"
    if not root.exists():
        return exts
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        enabled = (d / "enabled").exists()
        has_installer = (d / "install.sh").exists()
        desc = ""
        readme = d / "README.md"
        if readme.exists():
            for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                desc = line
                break
        exts.append(
            {
                "name": d.name,
                "enabled": "true" if enabled else "false",
                "description": desc,
                "has_installer": "true" if has_installer else "false",
            }
        )
    return exts


def load_services() -> dict:
    p = BASE_DIR / "config" / "resources" / "services.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def parse_env_exports(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def update_env_export(path: Path, key: str, value: str) -> None:
    key = key.strip()
    if not key:
        return
    lines = []
    found = False
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            lines.append(line)
            continue
        candidate = stripped
        if candidate.startswith("export "):
            candidate = candidate[len("export ") :].strip()
        if not candidate.startswith(f"{key}="):
            lines.append(line)
            continue
        lines.append(f'export {key}="{value}"')
        found = True
    if not found:
        lines.append(f'export {key}="{value}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_features_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().strip('"').strip("'")
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def load_features_state() -> tuple[dict[str, str], dict[str, str]]:
    base = parse_features_file(BASE_DIR / "config" / "features.yml")
    local = parse_features_file(BASE_DIR / "config" / "features.local.yml")
    return base, local


def normalize_feature_value(value: str) -> tuple[str, bool | None]:
    lowered = value.strip().lower()
    if lowered in ("true", "yes", "1", "on"):
        return "true", True
    if lowered in ("false", "no", "0", "off"):
        return "false", False
    return value, None


def save_features_local(overrides: dict[str, str]) -> None:
    path = BASE_DIR / "config" / "features.local.yml"
    lines = ["# Generated by dashboard overrides\n"]
    for key in sorted(overrides.keys()):
        val = overrides[key]
        lines.append(f"{key}: {val}\n")
    path.write_text("".join(lines), encoding="utf-8")


def update_feature_override(key: str, value: str) -> tuple[int, dict]:
    key = (key or "").strip()
    if not key:
        return 400, {"ok": False, "error": "missing feature key"}
    base, local = load_features_state()
    if key not in base:
        return 404, {"ok": False, "error": "unknown feature key"}
    value_norm, _ = normalize_feature_value(value)
    local[key] = value_norm
    save_features_local(local)
    merge = subprocess.run(
        [str(BASE_DIR / "scripts" / "83_features_merge.sh"), "--apply"],
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
    )
    sync = subprocess.run(
        [str(BASE_DIR / "scripts" / "13_features_sync.sh"), "--apply"],
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
    )
    return 200, {
        "ok": merge.returncode == 0 and sync.returncode == 0,
        "key": key,
        "value": value_norm,
        "merge_stdout": merge.stdout[-20000:],
        "merge_stderr": merge.stderr[-20000:],
        "sync_stdout": sync.stdout[-20000:],
        "sync_stderr": sync.stderr[-20000:],
    }


def load_tool_catalog() -> dict:
    path = BASE_DIR / "config" / "resources" / "tool_catalog.json"
    if not path.exists():
        return {"tools": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tools": []}


def catalog_items() -> list[dict]:
    data = load_tool_catalog()
    return data.get("tools") or []


def catalog_lookup(name: str) -> dict | None:
    for item in catalog_items():
        if item.get("name") == name:
            return item
    return None


def catalog_available(name: str, entrypoint: str | None) -> bool:
    cmd = entrypoint or name
    if not cmd:
        return False
    exe = shlex.split(cmd)[0]
    return shutil.which(exe) is not None


def load_capabilities_local() -> dict:
    path = BASE_DIR / "config" / "capabilities.local.json"
    if not path.exists():
        return {"capabilities": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"capabilities": {}}


def save_capability_template(cap_id: str, template: str) -> tuple[int, dict]:
    cap_id = (cap_id or "").strip()
    if not cap_id:
        return 400, {"ok": False, "error": "missing capability id"}
    if len(template) > 4000:
        return 400, {"ok": False, "error": "template too long (max 4000 chars)"}
    data = load_capabilities_local()
    caps = data.setdefault("capabilities", {})
    entry = caps.get(cap_id) or {}
    entry["cli_template"] = template
    caps[cap_id] = entry
    path = BASE_DIR / "config" / "capabilities.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return 200, {"ok": True, "capability": cap_id, "cli_template": template}


def list_services() -> list[dict]:
    registry = load_services().get("services", {}) or {}
    items = []
    for name, cfg in sorted(registry.items()):
        ports_raw = cfg.get("ports") or []
        port_keys: list[str] = []
        for entry in ports_raw:
            for match in re.findall(r"\\$\\{(PORT_[A-Z0-9_]+)", str(entry)):
                if match not in port_keys:
                    port_keys.append(match)
        items.append(
            {
                "name": name,
                "tier": cfg.get("tier", "core"),
                "profiles": cfg.get("profiles") or [],
                "image": cfg.get("image") or "",
                "ports": ports_raw,
                "port_keys": port_keys,
                "source": cfg.get("source") or "",
            }
        )
    return items


def read_log_file(path: Path, tail: int = 200) -> str:
    if not path.exists():
        return f"Log not found: {path}"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail_lines = lines[-tail:] if tail > 0 else lines
    return "\n".join(tail_lines)


def get_logs_for_app(app: str, tail: int = 200) -> str:
    app = app.strip().lower()
    if app == "dashboard":
        return read_log_file(BASE_DIR / "logs" / "dashboard.out.log", tail)
    if app == "comfyui":
        return read_log_file(BASE_DIR / "logs" / "comfyui.out.log", tail)
    if app == "comfyui_err":
        return read_log_file(BASE_DIR / "logs" / "comfyui.err.log", tail)
    if app == "dashboard_err":
        return read_log_file(BASE_DIR / "logs" / "dashboard.err.log", tail)
    return f"Unknown app log: {app}"


def docker_service_logs(service: str, tail: int = 200) -> tuple[int, dict]:
    compose_file = BASE_DIR / "docker-compose.yml"
    if not compose_file.exists():
        return 404, {"ok": False, "error": "Missing docker-compose.yml"}
    args = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "logs",
        f"--tail={tail}",
        service,
    ]
    p = subprocess.run(args, text=True, capture_output=True)
    return 200, {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "stdout": p.stdout[-20000:],
        "stderr": p.stderr[-20000:],
        "cmd": args,
    }


def ollama_analyze(prompt: str, model: str | None, cfg: dict) -> tuple[int, dict]:
    prompt = prompt.strip()
    if not prompt:
        return 400, {"ok": False, "error": "missing prompt"}
    base = cfg.get("AI_BEAST_OLLAMA") or ""
    if not base:
        port = cfg.get("PORT_OLLAMA") or "11434"
        base = f"http://127.0.0.1:{port}"
    model_name = model or cfg.get("AI_BEAST_OLLAMA_MODEL") or cfg.get("OLLAMA_MODEL")
    if not model_name:
        return 400, {"ok": False, "error": "missing model (set AI_BEAST_OLLAMA_MODEL)"}
    payload = json.dumps({"model": model_name, "prompt": prompt, "stream": False}).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{base}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        return 200, {"ok": True, "response": data.get("response", ""), "model": model_name}
    except urllib.error.HTTPError as exc:
        return 500, {"ok": False, "error": str(exc)}
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def get_llm_manager() -> LLMManager:
    return LLMManager(BASE_DIR)


def memory_info() -> dict[str, float]:
    info: dict[str, float] = {}
    try:
        if sys.platform == "darwin":
            total = int(
                subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.memsize"])
                .decode()
                .strip()
            )
            vm = subprocess.check_output(["/usr/bin/vm_stat"]).decode()
            page_size = 4096
            for line in vm.splitlines():
                if "page size of" in line:
                    page_size = int(line.split("page size of")[1].split("bytes")[0])
            pages = {}
            for line in vm.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k = k.strip().lower().replace(" ", "_")
                v = v.strip().strip(".")
                if v.isdigit():
                    pages[k] = int(v)
            free_pages = (
                pages.get("pages_free", 0)
                + pages.get("pages_inactive", 0)
                + pages.get("pages_speculative", 0)
            )
            free = free_pages * page_size
            used = max(total - free, 0)
            info = {
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "percent_used": round((used / total) * 100, 2) if total else 0.0,
            }
        elif sys.platform.startswith("linux"):
            total_kb = 0
            avail_kb = 0
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
            total = total_kb * 1024
            free = avail_kb * 1024
            used = max(total - free, 0)
            info = {
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "percent_used": round((used / total) * 100, 2) if total else 0.0,
            }
    except Exception:
        return info
    return info


def load_metrics() -> dict:
    try:
        from modules.monitoring import collect_metrics

        metrics = collect_metrics(BASE_DIR)
    except Exception as ex:
        metrics = {"error": str(ex)}
    metrics["memory"] = memory_info()
    return metrics


def run_beast(key):
    if key not in ALLOW:
        return 400, {"ok": False, "error": "Command not allowed"}
    if not BEAST.exists():
        return 500, {"ok": False, "error": f"Missing {BEAST}"}
    env = os.environ.copy()
    try:
        cfg = load_env_json()
        for k, v in cfg.items():
            if v is not None:
                env[k] = v
    except Exception as ex:
        return 500, {"ok": False, "error": f"Env load failed: {ex}"}
    args = [str(BEAST)] + ALLOW[key]
    p = subprocess.run(args, env=env, text=True, capture_output=True)
    return 200, {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "stdout": p.stdout[-20000:],
        "stderr": p.stderr[-20000:],
        "cmd": args,
    }


def update_paths(payload: dict) -> tuple[int, dict]:
    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "Invalid payload"}

    current = read_env_file(PATHS_ENV)
    guts_raw = payload.get("guts_dir") or current.get("GUTS_DIR") or current.get("BASE_DIR") or str(BASE_DIR)
    heavy_raw = payload.get("heavy_dir") or current.get("HEAVY_DIR") or str(BASE_DIR)

    ok, guts_dir = _sanitize_path(guts_raw, "GUTS_DIR")
    if not ok:
        return 400, {"ok": False, "error": guts_dir}
    ok, heavy_dir = _sanitize_path(heavy_raw, "HEAVY_DIR")
    if not ok:
        return 400, {"ok": False, "error": heavy_dir}

    if not BEAST.exists():
        return 500, {"ok": False, "error": f"Missing {BEAST}"}

    args = [
        str(BEAST),
        "init",
        "--apply",
        "--defaults",
        f"--guts-dir={guts_dir}",
        f"--heavy-dir={heavy_dir}",
    ]
    env = os.environ.copy()
    p = subprocess.run(args, env=env, text=True, capture_output=True)
    if p.returncode != 0:
        return 500, {
            "ok": False,
            "error": "init failed",
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-20000:],
        }

    try:
        cfg = load_env_json()
    except Exception as ex:
        cfg = {"error": str(ex)}

    return 200, {
        "ok": True,
        "returncode": p.returncode,
        "stdout": p.stdout[-20000:],
        "stderr": p.stderr[-20000:],
        "config": cfg,
    }


def install_extension(name: str) -> tuple[int, dict]:
    if not isinstance(name, str):
        return 400, {"ok": False, "error": "Invalid extension name"}
    ext = name.strip()
    if not ext or "/" in ext or "\\" in ext:
        return 400, {"ok": False, "error": "Invalid extension name"}
    ext_dir = BASE_DIR / "extensions" / ext
    installer = ext_dir / "install.sh"
    if not ext_dir.exists():
        return 404, {"ok": False, "error": f"Extension not found: {ext}"}
    if not installer.exists():
        return 400, {"ok": False, "error": f"Extension has no install.sh: {ext}"}

    try:
        cfg = load_env_json()
    except Exception:
        cfg = {}
    env = os.environ.copy()
    for k, v in cfg.items():
        if v is not None:
            env[k] = v

    args = [str(BEAST), "extensions", "install", ext, "--apply"]
    p = subprocess.run(args, env=env, text=True, capture_output=True)
    return 200, {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "stdout": p.stdout[-20000:],
        "stderr": p.stderr[-20000:],
        "cmd": args,
    }


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = urlparse(path).path
        if p in ("/", ""):
            return str(STATIC_DIR / "index.html")
        rel = Path(p.lstrip("/")).as_posix()
        full = (STATIC_DIR / rel).resolve()
        if not str(full).startswith(str(STATIC_DIR.resolve())):
            return str(STATIC_DIR / "index.html")
        return str(full)

    def _json(self, code, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        expected = read_token()
        if expected is None:
            return True
        supplied = (self.headers.get("X-Beast-Token", "") or "").strip()
        return secrets.compare_digest(supplied, expected)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/api/health":
            return self._json(200, {"ok": True, "base_dir": str(BASE_DIR)})
        if p.path == "/api/config":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "config": load_env_json()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/packs":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                packs = load_packs()
                features = load_features_env()
                items = []
                for name, meta in (packs.get("packs") or {}).items():
                    flag = pack_flag_name(name)
                    enabled = features.get(flag, "0") in ("1", "true", "True")
                    items.append(
                        {
                            "name": name,
                            "enabled": enabled,
                            "desc": meta.get("desc", ""),
                            "notes": meta.get("notes", ""),
                            "extensions": (meta.get("docker") or {}).get("extensions", []),
                        }
                    )
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/extensions":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "items": list_extensions()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/settings":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                env = parse_env_exports(BASE_DIR / "config" / "ai-beast.env")
                items = [
                    {
                        "key": "AI_BEAST_PROFILE",
                        "value": env.get("AI_BEAST_PROFILE", "full"),
                        "type": "select",
                        "options": ["lite", "full", "prodish"],
                        "description": "Runtime profile for native/docker services.",
                    },
                    {
                        "key": "AI_BEAST_PROFILE_SERVICES",
                        "value": env.get("AI_BEAST_PROFILE_SERVICES", "0"),
                        "type": "bool",
                        "description": "Include docker services from kryptos_project.yml profile.",
                    },
                    {
                        "key": "DOCKER_RUNTIME",
                        "value": env.get("DOCKER_RUNTIME", "auto"),
                        "type": "select",
                        "options": ["auto", "colima", "docker_desktop"],
                        "description": "Docker runtime selector.",
                    },
                ]
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/features":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                base, local = load_features_state()
                items = []
                for key, value in sorted(base.items()):
                    value_norm, bool_val = normalize_feature_value(value)
                    override = local.get(key)
                    override_norm = None
                    if override is not None:
                        override_norm, _ = normalize_feature_value(override)
                    current = override_norm if override_norm is not None else value_norm
                    _, current_bool = normalize_feature_value(current)
                    items.append(
                        {
                            "key": key,
                            "value": current,
                            "bool": current_bool is not None,
                            "enabled": current_bool,
                            "has_override": override is not None,
                            "base": value_norm,
                        }
                    )
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/services":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "items": list_services()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/list":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "items": list_tools()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/catalog":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                configured = load_tools_config().get("tools", {})
                items = []
                for entry in catalog_items():
                    name = entry.get("name") or ""
                    entrypoint = entry.get("entrypoint") or name
                    is_configured = name in configured
                    is_available = False
                    if is_configured:
                        existing = configured.get(name) or {}
                        is_available = catalog_available(
                            name,
                            existing.get("entrypoint") or existing.get("name") or name,
                        )
                    else:
                        is_available = catalog_available(name, entrypoint)
                    items.append(
                        {
                            **entry,
                            "configured": is_configured,
                            "available": is_available,
                        }
                    )
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/capabilities":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "items": list_capabilities()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/metrics":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "metrics": load_metrics()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/run":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            qs = parse_qs(p.query)
            key = (qs.get("cmd", [""])[0]).strip()
            code, obj = run_beast(key)
            return self._json(code, obj)
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/paths":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                code, obj = update_paths(data)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/extensions/install":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = data.get("name", "")
                code, obj = install_extension(name)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/toggle":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                kind = data.get("kind")
                name = data.get("name")
                enable = bool(data.get("enable"))
                if not kind or not name:
                    return self._json(400, {"ok": False, "error": "missing kind/name"})
                if kind == "extension":
                    cmd = ["extensions", "enable" if enable else "disable", name, "--apply"]
                elif kind == "pack":
                    cmd = ["packs", "enable" if enable else "disable", name, "--apply"]
                else:
                    return self._json(400, {"ok": False, "error": "invalid kind"})
                p = subprocess.run(
                    [str(BEAST)] + cmd,
                    env=os.environ.copy(),
                    text=True,
                    capture_output=True,
                )
                return self._json(
                    200,
                    {
                        "ok": p.returncode == 0,
                        "returncode": p.returncode,
                        "stdout": p.stdout[-20000:],
                        "stderr": p.stderr[-20000:],
                        "cmd": [str(BEAST)] + cmd,
                    },
                )
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/register":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = (data.get("name") or "").strip()
                if not name:
                    return self._json(400, {"ok": False, "error": "missing tool name"})
                source = (data.get("source") or "custom").strip()
                if source == "catalog":
                    entry = catalog_lookup(name)
                    if not entry:
                        return self._json(404, {"ok": False, "error": "tool not found in catalog"})
                    code, obj = update_tool_config(name, entry)
                    return self._json(code, obj)
                payload = {
                    "name": name,
                    "description": data.get("description") or "",
                    "entrypoint": data.get("entrypoint") or name,
                    "args": data.get("args") or "",
                    "cwd": data.get("cwd") or "",
                    "env": data.get("env") or {},
                    "test_command": data.get("test_command") or "",
                    "test_url": data.get("test_url") or "",
                    "install_command": data.get("install_command") or "",
                    "download_url": data.get("download_url") or "",
                    "config_hint": data.get("config_hint") or "",
                    "workflow": data.get("workflow") or "",
                    "category": data.get("category") or "",
                    "runner": data.get("runner") or "local",
                }
                code, obj = update_tool_config(name, payload)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/update":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = (data.get("name") or "").strip()
                if not name:
                    return self._json(400, {"ok": False, "error": "missing tool name"})
                updates = data.get("updates") or {}
                code, obj = update_tool_config(name, updates)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/install_bulk":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                names = data.get("names") or []
                run_installer = bool(data.get("run_installer", True))
                results = []
                cfg = load_tools_config().get("tools", {})
                for name in names:
                    name = str(name).strip()
                    if not name:
                        continue
                    if name not in cfg:
                        entry = catalog_lookup(name)
                        if entry:
                            update_tool_config(name, entry)
                            cfg[name] = entry
                        else:
                            results.append({"name": name, "ok": False, "error": "missing tool config"})
                            continue
                    code, obj = install_tool(name, run_installer)
                    results.append({"name": name, "status": code, **obj})
                return self._json(200, {"ok": True, "items": results})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/settings/set":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                key = (data.get("key") or "").strip()
                value = str(data.get("value", "")).strip()
                allowed = {"AI_BEAST_PROFILE", "AI_BEAST_PROFILE_SERVICES", "DOCKER_RUNTIME"}
                if key not in allowed:
                    return self._json(400, {"ok": False, "error": "unsupported setting"})
                path = BASE_DIR / "config" / "ai-beast.env"
                if not path.exists():
                    path.write_text("", encoding="utf-8")
                update_env_export(path, key, value)
                return self._json(200, {"ok": True, "key": key, "value": value})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/features/set":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                key = data.get("key")
                value = data.get("value", "")
                code, obj = update_feature_override(str(key), str(value))
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/run":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = data.get("name", "")
                entrypoint = data.get("entrypoint")
                args = data.get("args")
                code, obj = run_tool(name, entrypoint=entrypoint, args=args)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/install":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = data.get("name", "")
                run_installer = bool(data.get("run_installer"))
                code, obj = install_tool(name, run_installer)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/test":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = data.get("name", "")
                code, obj = run_tool_test(name)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/capabilities/template":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                cap_id = data.get("id", "")
                template = data.get("template") or ""
                code, obj = save_capability_template(str(cap_id), str(template))
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/services/logs":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                service = data.get("service")
                app = data.get("app")
                tail = int(data.get("tail", 200))
                if app:
                    output = get_logs_for_app(str(app), tail)
                    return self._json(200, {"ok": True, "stdout": output, "cmd": ["read_log", str(app)]})
                if service:
                    code, obj = docker_service_logs(str(service), tail)
                    return self._json(code, obj)
                return self._json(400, {"ok": False, "error": "missing service/app"})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/llm/analyze":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                prompt = data.get("prompt", "")
                model = data.get("model")
                cfg = load_env_json()
                code, obj = ollama_analyze(prompt, model, cfg)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/pull":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                model = data.get("model", "")
                if not model:
                    return self._json(400, {"ok": False, "error": "missing model"})
                res = get_llm_manager().pull_ollama_model(str(model))
                return self._json(200, res)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        return self._json(404, {"ok": False, "error": "not found"})


def main():
    host = "127.0.0.1"
    port = 8787
    try:
        cfg = load_env_json()
        if cfg.get("PORT_DASHBOARD"):
            port = int(cfg["PORT_DASHBOARD"])
    except Exception:
        pass
    os.chdir(str(STATIC_DIR))
    httpd = HTTPServer((host, port), Handler)
    print(f"[dashboard] http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
