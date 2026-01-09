#!/usr/bin/env bash
set -euo pipefail

# 87_queue.sh — enqueue or run RQ worker.

action="${1:-}"; shift || true
[[ -n "$action" ]] || { echo "Usage: 87_queue.sh {worker|enqueue|status} [--apply|--dry-run]"; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

# shellcheck disable=SC1091
source "$BASE_DIR/scripts/lib/common.sh"
parse_common_flags "${@:-}"

REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
QUEUE_NAME="${QUEUE_NAME:-default}"

case "$action" in
  worker)
    if [[ "${DRYRUN:-1}" -eq 1 ]]; then
      log "DRYRUN: python3 -m rq worker --url \"$REDIS_URL\" \"$QUEUE_NAME\""
      exit 0
    fi
    exec python3 -m rq worker --url "$REDIS_URL" "$QUEUE_NAME"
    ;;
  enqueue)
    task=""
    payload=""
    while [[ "${1:-}" =~ ^-- ]]; do
      case "$1" in
        --task) task="${2:-}"; shift 2 ;;
        --payload) payload="${2:-}"; shift 2 ;;
        *) break ;;
      esac
    done
    task="${task:-${1:-}}"
    [[ -n "$task" ]] || die "Usage: 87_queue.sh enqueue --task modules.queue.tasks.heartbeat [--payload '{\"args\":[],\"kwargs\":{}}']"
    if [[ "${DRYRUN:-1}" -eq 1 ]]; then
      log "DRYRUN: would enqueue $task with payload ${payload:-'{}'}"
      exit 0
    fi
    python3 - "$task" "${payload:-}" <<'PY'
import json
import sys

from modules.queue.rq_queue import enqueue_task

task = sys.argv[1]
payload_raw = sys.argv[2] if len(sys.argv) > 2 else ""
payload = {}
if payload_raw:
    payload = json.loads(payload_raw)
args = payload.get("args") or []
kwargs = payload.get("kwargs") or {}
result = enqueue_task(task, *args, **kwargs)
print(json.dumps(result))
PY
    ;;
  status)
    if [[ "${DRYRUN:-1}" -eq 1 ]]; then
      log "DRYRUN: python3 -m rq info --url \"$REDIS_URL\""
      exit 0
    fi
    python3 -m rq info --url "$REDIS_URL"
    ;;
  *)
    die "Usage: 87_queue.sh {worker|enqueue|status}"
    ;;
esac
