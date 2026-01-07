#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

source "$BASE_DIR/config/paths.env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true
[[ -f "$BASE_DIR/config/features.env" ]] && source "$BASE_DIR/config/features.env" || true

ok=0
fail=0

check(){
  local name="$1" cmd="$2"
  echo "[smoke] $name"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  ✅ ok"
    ok=$((ok+1))
  else
    echo "  ❌ fail"
    fail=$((fail+1))
  fi
}

# Native
if [[ "${FEATURE_NATIVE_OLLAMA:-1}" -eq 1 ]]; then
  check "ollama listening" "curl -fsS http://127.0.0.1:${PORT_OLLAMA:-11434}/api/tags"
fi

if [[ "${FEATURE_NATIVE_COMFYUI:-1}" -eq 1 ]]; then
  check "comfyui object_info" "curl -fsS http://127.0.0.1:${PORT_COMFYUI:-8188}/object_info"
fi

# Docker
if [[ "${FEATURE_DOCKER_QDRANT:-1}" -eq 1 ]]; then
  check "qdrant ready" "curl -fsS http://127.0.0.1:${PORT_QDRANT:-6333}/readyz"
fi

if [[ "${FEATURE_DOCKER_OPEN_WEBUI:-1}" -eq 1 ]]; then
  check "open-webui UI" "curl -fsS http://127.0.0.1:${PORT_WEBUI:-3000}/"
fi

if [[ "${FEATURE_DOCKER_UPTIME_KUMA:-0}" -eq 1 ]]; then
  check "uptime-kuma UI" "curl -fsS http://127.0.0.1:${PORT_KUMA:-3001}/"
fi

echo
echo "[smoke] ok=$ok fail=$fail"
[[ "$fail" -eq 0 ]]
