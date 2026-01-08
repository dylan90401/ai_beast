#!/usr/bin/env bash
set -euo pipefail

# 34_urls.sh — print service URLs from config/ports.env + ai-beast.env

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"

parse_common_flags "${@:-}"

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true
load_env_if_exists "$BASE_DIR/config/ai-beast.env"

bind_addr="${AI_BEAST_BIND_ADDR:-127.0.0.1}"
show_kv(){ printf "%-18s %s\n" "$1" "$2"; }

echo "AI Beast URLs"
echo
show_kv "Dashboard" "http://${bind_addr}:${PORT_DASHBOARD:-8787}"
show_kv "Open WebUI" "http://${bind_addr}:${PORT_WEBUI:-3000}"
show_kv "Ollama API" "http://${bind_addr}:${PORT_OLLAMA:-11434}"
show_kv "Qdrant" "http://${bind_addr}:${PORT_QDRANT:-6333}"
show_kv "ComfyUI" "http://${bind_addr}:${PORT_COMFYUI:-8188}"
show_kv "n8n" "http://${bind_addr}:${PORT_N8N:-5678}"
show_kv "Uptime Kuma" "http://${bind_addr}:${PORT_KUMA:-3001}"
show_kv "Portainer" "http://${bind_addr}:${PORT_PORTAINER:-9000}"
show_kv "Langflow" "http://${bind_addr}:${PORT_LANGFLOW:-7860}"
show_kv "Flowise" "http://${bind_addr}:${PORT_FLOWISE:-3003}"
show_kv "Dify" "http://${bind_addr}:${PORT_DIFY:-3004}"
show_kv "SearxNG" "http://${bind_addr}:${PORT_SEARXNG:-8088}"
show_kv "Apache Tika" "http://${bind_addr}:${PORT_TIKA:-9998}"
show_kv "Unstructured API" "http://${bind_addr}:${PORT_UNSTRUCTURED:-8000}"
show_kv "OTel HTTP" "http://${bind_addr}:${PORT_OTEL_HTTP:-4318}"
show_kv "MinIO API" "http://${bind_addr}:${PORT_MINIO:-9001}"
show_kv "MinIO Console" "http://${bind_addr}:${PORT_MINIO_CONSOLE:-9002}"
show_kv "Speech API" "http://${bind_addr}:${PORT_SPEECH_API:-9977}"
