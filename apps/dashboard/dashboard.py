#!/usr/bin/env python3
import json
import os
import secrets
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def resolve_base_dir():
    bd = os.environ.get("BASE_DIR")
    if bd:
        return Path(bd)
    here = Path(__file__).resolve()
    return here.parents[3]  # .../apps/dashboard/_template/dashboard.py -> project root


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


def read_token():
    if not TOKEN_FILE.exists():
        return None
    t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t or None


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


def load_services() -> dict:
    p = BASE_DIR / "config" / "resources" / "services.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


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
