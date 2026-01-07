#!/usr/bin/env bash
set -euo pipefail

# 32_status.sh — show URLs, enabled packs/ext, and basic health probes.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/docker_runtime.sh"

AI_BEAST_LOG_PREFIX="status"
parse_common_flags "${@:-}"

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true
[[ -f "$BASE_DIR/config/profiles.env" ]] && source "$BASE_DIR/config/profiles.env" || true
load_env_if_exists "$BASE_DIR/config/ai-beast.env"
load_env_if_exists "$BASE_DIR/config/features.env"

bind_addr="${AI_BEAST_BIND_ADDR:-127.0.0.1}"
profile="${AI_BEAST_PROFILE:-full}"

rt="$(docker_runtime_choice)"
rt_ready="no"
docker_runtime_is_ready && rt_ready="yes" || true

show_kv(){ printf "%-18s %s\n" "$1" "$2"; }

probe(){
  local name="$1" url="$2"
  if ! have_cmd curl; then
    printf "%-18s %s\n" "$name" "curl missing"
    return 0
  fi
  if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
    printf "%-18s %s\n" "$name" "ok"
  else
    printf "%-18s %s\n" "$name" "down"
  fi
}

echo "AI Beast status"
echo
show_kv "BASE_DIR" "$BASE_DIR"
show_kv "PROFILE" "$profile"
show_kv "DOCKER_RUNTIME" "$rt (ready=$rt_ready)"
show_kv "BIND_ADDR" "$bind_addr"
echo

# Ports (single source of truth)
show_kv "PORT_WEBUI" "${PORT_WEBUI:-3000}"
show_kv "PORT_OLLAMA" "${PORT_OLLAMA:-11434}"
show_kv "PORT_QDRANT" "${PORT_QDRANT:-6333}"
show_kv "PORT_COMFYUI" "${PORT_COMFYUI:-8188}"
show_kv "PORT_N8N" "${PORT_N8N:-5678}"
show_kv "PORT_KUMA" "${PORT_KUMA:-3001}"
show_kv "PORT_PORTAINER" "${PORT_PORTAINER:-9000}"
show_kv "PORT_LANGFLOW" "${PORT_LANGFLOW:-7860}"
show_kv "PORT_FLOWISE" "${PORT_FLOWISE:-3003}"
show_kv "PORT_DIFY" "${PORT_DIFY:-3004}"
show_kv "PORT_TIKA" "${PORT_TIKA:-9998}"
show_kv "PORT_UNSTRUCTURED" "${PORT_UNSTRUCTURED:-8000}"
show_kv "PORT_OTEL_GRPC" "${PORT_OTEL_GRPC:-4317}"
show_kv "PORT_OTEL_HTTP" "${PORT_OTEL_HTTP:-4318}"
show_kv "PORT_MINIO" "${PORT_MINIO:-9001}"
show_kv "PORT_MINIO_CONSOLE" "${PORT_MINIO_CONSOLE:-9002}"
echo

# URLs
echo "URLs"
show_kv "Open WebUI" "http://${bind_addr}:${PORT_WEBUI:-3000}"
show_kv "Ollama API" "http://${bind_addr}:${PORT_OLLAMA:-11434}"
show_kv "Qdrant" "http://${bind_addr}:${PORT_QDRANT:-6333}"
show_kv "ComfyUI" "http://${bind_addr}:${PORT_COMFYUI:-8188}"
show_kv "n8n" "http://${bind_addr}:${PORT_N8N:-5678}"
show_kv "Uptime Kuma" "http://${bind_addr}:${PORT_KUMA:-3001}"
show_kv "Portainer" "http://${bind_addr}:${PORT_PORTAINER:-9000}"
show_kv "Langflow" "http://${bind_addr}:${PORT_LANGFLOW:-7860}"
show_kv "Flowise" "http://${bind_addr}:${PORT_FLOWISE:-3003}"
show_kv "Dify (stub)" "http://${bind_addr}:${PORT_DIFY:-3004}"
show_kv "Apache Tika (stub)" "http://${bind_addr}:${PORT_TIKA:-9998}"
show_kv "Unstructured (stub)" "http://${bind_addr}:${PORT_UNSTRUCTURED:-8000}"
show_kv "OTel gRPC" "${bind_addr}:${PORT_OTEL_GRPC:-4317}"
show_kv "OTel HTTP" "http://${bind_addr}:${PORT_OTEL_HTTP:-4318}"
show_kv "MinIO API" "http://${bind_addr}:${PORT_MINIO:-9001}"
show_kv "MinIO Console" "http://${bind_addr}:${PORT_MINIO_CONSOLE:-9002}"
echo

# Enabled packs/extensions from state.json (if present)
if [[ -f "$BASE_DIR/config/state.json" ]] && have_cmd jq; then
  echo "Desired state"
  jq -r '.desired.packs_enabled[]?' "$BASE_DIR/config/state.json" 2>/dev/null | sed 's/^/  pack: /' || true
  jq -r '.desired.extensions_enabled[]?' "$BASE_DIR/config/state.json" 2>/dev/null | sed 's/^/  ext:  /' || true
  echo
fi

# Enabled markers on disk
if [[ -d "$BASE_DIR/extensions" ]]; then
  echo "Extensions (enabled markers)"
  find "$BASE_DIR/extensions" -mindepth 2 -maxdepth 2 -type f -name enabled -print 2>/dev/null | \
    sed 's#.*/extensions/##; s#/enabled##' | sort | sed 's/^/  /' || true
  echo
fi

# Quick health probes
echo "Health"
probe "ollama" "http://${bind_addr}:${PORT_OLLAMA:-11434}/api/version"
probe "qdrant" "http://${bind_addr}:${PORT_QDRANT:-6333}/healthz"
probe "open-webui" "http://${bind_addr}:${PORT_WEBUI:-3000}/health"
probe "comfyui" "http://${bind_addr}:${PORT_COMFYUI:-8188}/"
probe "otel-http" "http://${bind_addr}:${PORT_OTEL_HTTP:-4318}/"
probe "minio" "http://${bind_addr}:${PORT_MINIO:-9001}/minio/health/ready"
echo

echo "Next action: ./bin/beast doctor  (for deeper diagnostics)"
