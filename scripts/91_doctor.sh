#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# best effort loads
source "$BASE_DIR/config/paths.env" 2>/dev/null || true
source "$BASE_DIR/config/ports.env" 2>/dev/null || true
source "$BASE_DIR/config/features.env" 2>/dev/null || true

ok(){ echo "[doctor] OK: $*"; }
warn(){ echo "[doctor] WARN: $*"; }
fail(){ echo "[doctor] FAIL: $*"; }

cmd(){ command -v "$1" >/dev/null 2>&1; }

echo "== AI Beast Doctor =="
if [[ -f "$BASE_DIR/config/paths.env" ]]; then
  ok "paths.env present"
else
  fail "missing config/paths.env (run beast init --apply)"
fi

if cmd git; then ok "git"; else warn "git missing"; fi
if cmd python3; then ok "python3"; else warn "python3 missing"; fi
if cmd docker; then ok "docker"; else warn "docker missing (only needed for docker services)"; fi
if cmd ollama; then ok "ollama"; else warn "ollama missing"; fi

if [[ -d "${COMFYUI_DIR:-}" ]]; then
  ok "ComfyUI dir: $COMFYUI_DIR"
else
  warn "ComfyUI not installed at COMFYUI_DIR"
fi

if [[ -d "${VENV_DIR:-}" ]]; then
  ok "venv: $VENV_DIR"
else
  warn "venv missing (run beast bootstrap --apply)"
fi

curl_check(){
  local name="$1" url="$2"
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then ok "$name reachable"; else warn "$name not reachable: $url"; fi
  fi
}

[[ -n "${PORT_COMFYUI:-}" ]] && curl_check "ComfyUI" "http://127.0.0.1:${PORT_COMFYUI}/" || true
[[ -n "${PORT_OLLAMA:-}" ]] && curl_check "Ollama" "http://127.0.0.1:${PORT_OLLAMA}/api/tags" || true
[[ -n "${PORT_QDRANT:-}" ]] && curl_check "Qdrant" "http://127.0.0.1:${PORT_QDRANT}/" || true
[[ -n "${PORT_WEBUI:-}" ]] && curl_check "Open WebUI" "http://127.0.0.1:${PORT_WEBUI}/" || true
[[ -n "${PORT_SEARXNG:-}" ]] && curl_check "SearXNG" "http://127.0.0.1:${PORT_SEARXNG}/" || true

echo
echo "Packs enabled (features.env):"
grep -E '^export +FEATURE_PACKS_' "$BASE_DIR/config/features.env" 2>/dev/null || echo "  (none)"
