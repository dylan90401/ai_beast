#!/usr/bin/env python3
import json
import os
import secrets
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from modules.capabilities.registry import list_capabilities, run_capability_checks
from modules.core.metadata_db import get_metadata_db
from modules.queue.rq_queue import enqueue_task
from modules.tools.registry import (
    extract_all_tools,
    extract_tool,
    install_tool,
    list_tools,
    run_tool,
    save_tool_config,
    tool_manifest,
)


def resolve_base_dir():
    bd = os.environ.get("BASE_DIR")
    if bd:
        return Path(bd)
    here = Path(__file__).resolve()
    if here.parent.name == "_template":
        return here.parents[3]
    return here.parents[2]


BASE_DIR = resolve_base_dir()
PATHS_ENV = BASE_DIR / "config" / "paths.env"
PORTS_ENV = BASE_DIR / "config" / "ports.env"
TOKEN_FILE = BASE_DIR / "config" / "secrets" / "dashboard_token.txt"
HF_TOKEN_FILE = BASE_DIR / "config" / "secrets" / "hf_token.txt"
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


def read_token():
    if not TOKEN_FILE.exists():
        return None
    t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t or None


def read_hf_token() -> str | None:
    if not HF_TOKEN_FILE.exists():
        return None
    t = HF_TOKEN_FILE.read_text(encoding="utf-8", errors="replace").strip()
    return t or None


def write_hf_token(token: str | None) -> None:
    HF_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if token:
        HF_TOKEN_FILE.write_text(token, encoding="utf-8")
    elif HF_TOKEN_FILE.exists():
        HF_TOKEN_FILE.unlink()


def load_env_json():
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
    return json.loads(out)


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


def extension_enabled_map() -> dict[str, bool]:
    return {e["name"]: e["enabled"] == "true" for e in list_extensions()}


def load_services() -> dict:
    p = BASE_DIR / "config" / "resources" / "services.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def docker_ps() -> list[dict[str, str]]:
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Ports}}|{{.Image}}"],
            text=True,
        )
    except Exception:
        return []
    items = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        name, status, ports, image = parts
        items.append(
            {
                "name": name.strip(),
                "status": status.strip(),
                "ports": ports.strip(),
                "image": image.strip(),
            }
        )
    return items


def docker_logs(name: str, tail: int = 200) -> tuple[bool, str]:
    if not name or any(ch in name for ch in ("/", " ", "\t")):
        return False, "Invalid container name"
    containers = {c["name"] for c in docker_ps()}
    if name not in containers:
        return False, f"Container not running: {name}"
    try:
        out = subprocess.check_output(
            ["docker", "logs", "--tail", str(tail), name],
            text=True,
            stderr=subprocess.STDOUT,
        )
        return True, out[-20000:]
    except subprocess.CalledProcessError as ex:
        return False, (ex.output or str(ex))[-20000:]


def validate_urls(payload: dict) -> tuple[int, dict]:
    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "Invalid payload"}
    checks = payload.get("checks") or []
    if not isinstance(checks, list):
        return 400, {"ok": False, "error": "checks must be a list"}
    results = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        if not name or not url:
            results.append({"name": name or "unknown", "url": url, "ok": False, "error": "missing name/url"})
            continue
        try:
            req = Request(url, headers={"User-Agent": "ai-beast-dashboard"})
            with urlopen(req, timeout=3) as resp:
                status = resp.status
                results.append({"name": name, "url": url, "ok": 200 <= status < 400, "status": status})
        except Exception as ex:
            results.append({"name": name, "url": url, "ok": False, "error": str(ex)})
    return 200, {"ok": True, "results": results}


def list_ai_tools() -> list[dict[str, str]]:
    return list_tools(BASE_DIR)


def reveal_path(path: Path) -> tuple[int, dict]:
    if not path.exists():
        return 404, {"ok": False, "error": f"Path not found: {path}"}
    try:
        p = subprocess.run(["/usr/bin/open", str(path)], text=True, capture_output=True)
        return 200, {"ok": p.returncode == 0, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except Exception as ex:
        return 500, {"ok": False, "error": str(ex)}


def extract_all_ai_tools(run_installer: bool = False) -> tuple[int, dict]:
    return extract_all_tools(run_installer, base=BASE_DIR)


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
    try:
        metrics["metadata_db"] = get_metadata_db().status()
    except Exception as ex:
        metrics["metadata_db"] = {"ok": False, "error": str(ex)}
    return metrics


def record_dashboard_event(name: str, payload: dict) -> None:
    try:
        get_metadata_db().record_event("dashboard", name, payload)
    except Exception:
        pass


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
    record_dashboard_event(
        "beast_command",
        {"command": key, "returncode": p.returncode, "ok": p.returncode == 0},
    )
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


def pack_enabled(name: str, features: dict[str, str]) -> bool:
    flag = pack_flag_name(name)
    return features.get(flag, "0") in ("1", "true", "True")


def capability_with_status(cap: dict, features: dict[str, str], ext_map: dict[str, bool]) -> dict:
    packs = cap.get("packs") or []
    exts = cap.get("extensions") or []
    packs_ok = all(pack_enabled(p, features) for p in packs)
    exts_ok = all(ext_map.get(e, False) for e in exts)
    item = {**cap}
    item["enabled"] = bool(packs_ok and exts_ok)
    return item


# LLM Model Manager singleton
_llm_manager = None


def get_llm_manager():
    global _llm_manager
    if _llm_manager is None:
        try:
            from modules.llm import LLMManager
            _llm_manager = LLMManager(BASE_DIR)
        except ImportError:
            return None
    return _llm_manager


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
        if p.path == "/metrics":
            try:
                from modules.monitoring import render_prometheus_metrics

                body = render_prometheus_metrics(load_metrics())
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/hf_token":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            token = read_hf_token()
            return self._json(200, {"ok": True, "set": token is not None})
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
        if p.path == "/api/services":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "services": load_services()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/metrics":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "metrics": load_metrics()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/docker/ps":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "containers": docker_ps()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/docker/logs":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            qs = parse_qs(p.query)
            name = (qs.get("name", [""])[0]).strip()
            tail_raw = (qs.get("tail", ["200"])[0]).strip()
            try:
                tail = max(10, min(2000, int(tail_raw)))
            except ValueError:
                tail = 200
            ok, data = docker_logs(name, tail)
            code = 200 if ok else 400
            return self._json(code, {"ok": ok, "name": name, "logs": data})
        if p.path == "/api/capabilities":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                features = load_features_env()
                ext_map = extension_enabled_map()
                caps = [capability_with_status(c, features, ext_map) for c in list_capabilities(BASE_DIR)]
                return self._json(200, {"ok": True, "items": caps})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, {"ok": True, "tools": list_ai_tools()})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/config":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            qs = parse_qs(p.query)
            name = (qs.get("name", [""])[0]).strip()
            if not name:
                return self._json(400, {"ok": False, "error": "missing name"})
            try:
                cfg = list_ai_tools()
                match = next((t for t in cfg if t["name"] == name), None)
                if not match:
                    return self._json(404, {"ok": False, "error": "Tool not found"})
                return self._json(200, {"ok": True, "tool": match})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/manifest":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                return self._json(200, tool_manifest(BASE_DIR))
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/run":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            qs = parse_qs(p.query)
            key = (qs.get("cmd", [""])[0]).strip()
            code, obj = run_beast(key)
            return self._json(code, obj)
        # LLM Models API
        if p.path == "/api/models":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                qs = parse_qs(p.query)
                force = qs.get("force", ["0"])[0] in ("1", "true")
                models = [m.to_dict() for m in mgr.list_all_models(force_scan=force)]
                ollama_running = mgr.ollama_running()
                return self._json(200, {"ok": True, "models": models, "ollama_running": ollama_running})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/available":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                models = mgr.list_available_ollama_models()
                return self._json(200, {"ok": True, "models": models})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/storage":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                info = mgr.get_storage_info()
                return self._json(200, {"ok": True, "storage": info})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/downloads":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                qs = parse_qs(p.query)
                download_id = qs.get("id", [None])[0]
                status = mgr.get_download_status(download_id)
                return self._json(200, {"ok": True, "downloads": status})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/registry":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                items = get_metadata_db().list_models()
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/registry/versions":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                qs = parse_qs(p.query)
                name = (qs.get("name", [""])[0]).strip()
                if not name:
                    return self._json(400, {"ok": False, "error": "missing name"})
                items = get_metadata_db().list_versions(name)
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/validate":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                code, obj = validate_urls(data)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/extract":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                name = str(data.get("name") or "").strip()
                code, obj = extract_tool(name, base=BASE_DIR)
                record_dashboard_event("tool_extract", {"name": name, "ok": obj.get("ok", False)})
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/install":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                name = str(data.get("name") or "").strip()
                run_installer = bool(data.get("run_installer"))
                code, obj = install_tool(name, run_installer, base=BASE_DIR)
                record_dashboard_event(
                    "tool_install",
                    {"name": name, "ok": obj.get("ok", False), "run_installer": run_installer},
                )
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/extract_all":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                run_installer = bool(data.get("run_installer"))
                code, obj = extract_all_ai_tools(run_installer)
                record_dashboard_event(
                    "tool_extract_all",
                    {"ok": obj.get("ok", False), "run_installer": run_installer},
                )
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/open":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                name = str(data.get("name") or "").strip()
                if not name or "/" in name or "\\" in name:
                    return self._json(400, {"ok": False, "error": "Invalid tool name"})
                target = BASE_DIR / "_ai_tools" / "extracted" / name
                code, obj = reveal_path(target)
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/run":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                allow = bool(data.get("allow"))
                if not allow:
                    return self._json(403, {"ok": False, "error": "Tool runs are sandboxed by default. Enable Allow to run."})
                name = str(data.get("name") or "").strip()
                entrypoint = data.get("entrypoint")
                args = data.get("args")
                code, obj = run_tool(name, mode="run", entrypoint=entrypoint, args=args, base=BASE_DIR)
                record_dashboard_event("tool_run", {"name": name, "ok": obj.get("ok", False)})
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/test":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                allow = bool(data.get("allow"))
                if not allow:
                    return self._json(403, {"ok": False, "error": "Tool runs are sandboxed by default. Enable Allow to run."})
                name = str(data.get("name") or "").strip()
                code, obj = run_tool(name, mode="test", base=BASE_DIR)
                record_dashboard_event("tool_test", {"name": name, "ok": obj.get("ok", False)})
                return self._json(code, obj)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/queue/enqueue":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                task = (data.get("task") or "").strip()
                if not task:
                    return self._json(400, {"ok": False, "error": "Missing task"})
                args = data.get("args") or []
                kwargs = data.get("kwargs") or {}
                result = enqueue_task(task, *args, **kwargs)
                record_dashboard_event("queue_enqueue", {"task": task, "ok": result.get("ok", False)})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/queue/jobs":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                from modules.queue.rq_queue import list_jobs

                qs = parse_qs(p.query)
                limit_raw = (qs.get("limit", ["25"])[0]).strip()
                status_raw = (qs.get("status", [""])[0]).strip()
                try:
                    limit = int(limit_raw)
                except ValueError:
                    limit = 25
                items = list_jobs(limit=limit, status=status_raw)
                return self._json(200, {"ok": True, "items": items})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/queue/cleanup":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                from modules.queue.rq_queue import cleanup_jobs

                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                status = (data.get("status") or "").strip().lower()
                limit_raw = data.get("limit", 200)
                try:
                    limit = int(limit_raw)
                except (ValueError, TypeError):
                    limit = 200
                result = cleanup_jobs(status=status, limit=limit)
                record_dashboard_event(
                    "queue_cleanup",
                    {"status": status, "count": result.get("count", 0), "ok": result.get("ok", False)},
                )
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/queue/retry":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                from modules.queue.rq_queue import retry_job

                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                job_id = (data.get("job_id") or "").strip()
                result = retry_job(job_id)
                record_dashboard_event("queue_retry", {"job_id": job_id, "ok": result.get("ok", False)})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/queue/delete":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                from modules.queue.rq_queue import delete_job

                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                job_id = (data.get("job_id") or "").strip()
                result = delete_job(job_id)
                record_dashboard_event("queue_delete", {"job_id": job_id, "ok": result.get("ok", False)})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/capabilities/check":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                cap_id = (data.get("id") or "").strip() or None
                allow_tool_runs = bool(data.get("allow_tool_runs"))
                cfg = load_env_json()
                results = run_capability_checks(cfg, cap_id, allow_tool_runs, base=BASE_DIR)
                record_dashboard_event(
                    "capability_check",
                    {"id": cap_id or "all", "count": len(results), "allow": allow_tool_runs},
                )
                return self._json(200, {"ok": True, "results": results})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/capabilities/toggle":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                cap_id = str(data.get("id") or "").strip()
                enable = bool(data.get("enable"))
                if not cap_id:
                    return self._json(400, {"ok": False, "error": "missing id"})
                cap = next((c for c in list_capabilities(BASE_DIR) if c.get("id") == cap_id), None)
                if not cap:
                    return self._json(404, {"ok": False, "error": "capability not found"})
                cmds = []
                for pack in cap.get("packs") or []:
                    cmds.append(["packs", "enable" if enable else "disable", pack, "--apply"])
                for ext in cap.get("extensions") or []:
                    cmds.append(["extensions", "enable" if enable else "disable", ext, "--apply"])
                outputs = []
                for cmd in cmds:
                    proc = subprocess.run([str(BEAST)] + cmd, text=True, capture_output=True)
                    outputs.append(
                        {
                            "cmd": [str(BEAST)] + cmd,
                            "returncode": proc.returncode,
                            "stdout": proc.stdout[-20000:],
                            "stderr": proc.stderr[-20000:],
                            "ok": proc.returncode == 0,
                        }
                    )
                ok = all(o["ok"] for o in outputs) if outputs else True
                record_dashboard_event("capability_toggle", {"id": cap_id, "enable": enable, "ok": ok})
                return self._json(200, {"ok": ok, "results": outputs})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/tools/config":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                name = str(data.get("name") or "").strip()
                cfg = data.get("config")
                if not name or not isinstance(cfg, dict):
                    return self._json(400, {"ok": False, "error": "missing name/config"})
                save_tool_config(name, cfg, base=BASE_DIR)
                updated = list_ai_tools()
                match = next((t for t in updated if t["name"] == name), None)
                return self._json(200, {"ok": True, "tool": match})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/hf_token":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body or "{}")
                raw = (data.get("token") or "").strip()
                if not raw:
                    write_hf_token(None)
                    return self._json(200, {"ok": True, "set": False, "message": "HF token cleared"})
                if "\n" in raw or "\r" in raw:
                    return self._json(400, {"ok": False, "error": "Token cannot be multiline"})
                if raw.lower().startswith("hf_"):
                    write_hf_token(raw)
                    return self._json(200, {"ok": True, "set": True})
                write_hf_token(raw)
                return self._json(200, {"ok": True, "set": True, "warning": "Token saved, but does not look like an HF token (expected to start with hf_)"})
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/paths":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                code, obj = update_paths(data)
                record_dashboard_event(
                    "paths_update",
                    {"ok": obj.get("ok", False), "guts_dir": data.get("guts_dir"), "heavy_dir": data.get("heavy_dir")},
                )
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
                record_dashboard_event("extension_install", {"name": name, "ok": obj.get("ok", False)})
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
                record_dashboard_event(
                    "toggle",
                    {"kind": kind, "name": name, "enable": enable, "ok": p.returncode == 0},
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
        # LLM Model operations
        if p.path == "/api/models/pull":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                model_name = data.get("model")
                if not model_name:
                    return self._json(400, {"ok": False, "error": "Missing model name"})
                result = mgr.pull_ollama_model(model_name)
                record_dashboard_event("model_pull", {"model": model_name, "ok": result.get("ok", False)})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/delete":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                path = data.get("path", "")
                if path.startswith("ollama:"):
                    model_name = path.replace("ollama:", "")
                    result = mgr.delete_ollama_model(model_name)
                else:
                    result = mgr.delete_local_model(path)
                record_dashboard_event("model_delete", {"path": path, "ok": result.get("ok", False)})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/download":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                url = data.get("url")
                if not url:
                    return self._json(400, {"ok": False, "error": "Missing URL"})
                filename = data.get("filename")
                destination = data.get("destination", "internal")
                custom_path = data.get("custom_path")
                from modules.llm import ModelLocation
                loc_map = {
                    "internal": ModelLocation.INTERNAL,
                    "external": ModelLocation.EXTERNAL,
                    "custom": ModelLocation.CUSTOM,
                }
                loc = loc_map.get(destination, ModelLocation.INTERNAL)
                result = mgr.download_from_url(url, filename, loc, custom_path)
                record_dashboard_event(
                    "model_download",
                    {"destination": destination, "ok": result.get("ok", False)},
                )
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/registry/register":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = (data.get("name") or "").strip()
                version = (data.get("version") or "v1").strip()
                if not name:
                    return self._json(400, {"ok": False, "error": "Missing name"})
                result = get_metadata_db().register_model(
                    name=name,
                    version=version,
                    kind=str(data.get("kind") or ""),
                    path=str(data.get("path") or ""),
                    checksum=str(data.get("checksum") or ""),
                    source_url=str(data.get("source_url") or ""),
                    notes=str(data.get("notes") or ""),
                )
                record_dashboard_event("model_register", {"name": name, "version": version})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/registry/rollback":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                name = (data.get("name") or "").strip()
                version = (data.get("version") or "").strip()
                if not name or not version:
                    return self._json(400, {"ok": False, "error": "Missing name/version"})
                result = get_metadata_db().rollback_model(name, version)
                record_dashboard_event("model_rollback", {"name": name, "version": version, "ok": result.get("ok", False)})
                return self._json(200, result)
            except Exception as ex:
                return self._json(500, {"ok": False, "error": str(ex)})
        if p.path == "/api/models/move":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            mgr = get_llm_manager()
            if not mgr:
                return self._json(500, {"ok": False, "error": "LLM module not available"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else "{}"
                data = json.loads(body)
                src_path = data.get("path")
                destination = data.get("destination", "internal")
                custom_path = data.get("custom_path")
                if not src_path:
                    return self._json(400, {"ok": False, "error": "Missing path"})
                from modules.llm import ModelLocation
                loc_map = {
                    "internal": ModelLocation.INTERNAL,
                    "external": ModelLocation.EXTERNAL,
                    "custom": ModelLocation.CUSTOM,
                }
                loc = loc_map.get(destination, ModelLocation.INTERNAL)
                result = mgr.move_model(src_path, loc, custom_path)
                record_dashboard_event(
                    "model_move",
                    {"path": src_path, "destination": destination, "ok": result.get("ok", False)},
                )
                return self._json(200, result)
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
