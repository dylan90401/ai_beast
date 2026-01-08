#!/usr/bin/env python3
import json
import os
import secrets
import subprocess
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
}


def read_token():
    if not TOKEN_FILE.exists():
        return None
    t = TOKEN_FILE.read_text(encoding="utf-8").strip()
    return t or None


def load_env_json():
    script = f'''
set -euo pipefail
source "{PATHS_ENV}"
[ -f "{PORTS_ENV}" ] && source "{PORTS_ENV}" || true
python3 - <<'PY'
import os, json
keys=["BASE_DIR","MODELS_DIR","DATA_DIR","OUTPUTS_DIR","CACHE_DIR","BACKUP_DIR","LOG_DIR","COMFYUI_DIR","VENV_DIR",
      "PORT_WEBUI","PORT_COMFYUI","PORT_QDRANT","PORT_OLLAMA","PORT_DASHBOARD","AI_BEAST_PROFILE"]
print(json.dumps({{k: os.environ.get(k) for k in keys}}))
PY
'''
    out = subprocess.check_output(["/bin/bash", "-lc", script], text=True)
    return json.loads(out)


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
        if p.path == "/api/run":
            if not self._auth():
                return self._json(401, {"ok": False, "error": "Unauthorized"})
            qs = parse_qs(p.query)
            key = (qs.get("cmd", [""])[0]).strip()
            code, obj = run_beast(key)
            return self._json(code, obj)
        return super().do_GET()


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
