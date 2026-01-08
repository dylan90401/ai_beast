#!/usr/bin/env bash
set -euo pipefail

mode="${1:-status}"; shift || true

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true

curl_ok(){
  local url="$1"
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

status(){
  echo "[health] Dashboard: http://127.0.0.1:${PORT_DASHBOARD:-8787}  => $(curl_ok "http://127.0.0.1:${PORT_DASHBOARD:-8787}/api/health" && echo OK || echo DOWN)"
  echo "[health] ComfyUI:    http://127.0.0.1:${PORT_COMFYUI:-8188}  => $(curl_ok "http://127.0.0.1:${PORT_COMFYUI:-8188}/" && echo OK || echo DOWN)"
  echo "[health] Ollama:     http://127.0.0.1:${PORT_OLLAMA:-11434}  => $(curl_ok "http://127.0.0.1:${PORT_OLLAMA:-11434}/api/tags" && echo OK || echo DOWN)"
  echo "[health] WebUI:      http://127.0.0.1:${PORT_WEBUI:-3000}     => $(curl_ok "http://127.0.0.1:${PORT_WEBUI:-3000}/" && echo OK || echo DOWN)"
  echo "[health] Qdrant:     http://127.0.0.1:${PORT_QDRANT:-6333}    => $(curl_ok "http://127.0.0.1:${PORT_QDRANT:-6333}/healthz" && echo OK || echo DOWN)"
}

doctor(){
  list_recent_logs(){
    local logs_dir="$BASE_DIR/logs"
    [[ -d "$logs_dir" ]] || return 0
    if stat -f "%m" "$logs_dir" >/dev/null 2>&1; then
      while IFS= read -r -d '' file; do
        printf '%s %s\n' "$(stat -f "%m" "$file")" "$file"
      done < <(find "$logs_dir" -maxdepth 1 -type f -print0 2>/dev/null)
    else
      while IFS= read -r -d '' file; do
        printf '%s %s\n' "$(stat -c "%Y" "$file")" "$file"
      done < <(find "$logs_dir" -maxdepth 1 -type f -print0 2>/dev/null)
    fi | sort -rn | head -n 10 | cut -d' ' -f2- | sed 's/^/[doctor] /'
  }

  echo "[doctor] Listening ports:"
  for p in "${PORT_DASHBOARD:-8787}" "${PORT_COMFYUI:-8188}" "${PORT_OLLAMA:-11434}" "${PORT_WEBUI:-3000}" "${PORT_QDRANT:-6333}"; do
    lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | sed "s/^/[doctor] /" || echo "[doctor] port $p: not listening"
  done
  echo "[doctor] Recent logs:"
  list_recent_logs || true
}

case "$mode" in
  status) status ;;
  doctor) doctor ;;
  *) echo "Usage: 40_healthcheck.sh {status|doctor}"; exit 1 ;;
esac
