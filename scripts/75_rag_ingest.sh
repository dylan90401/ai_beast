#!/usr/bin/env bash
set -euo pipefail

APPLY=0
DIR=""
COLLECTION="ai_beast"
QDRANT_URL="http://127.0.0.1:${PORT_QDRANT:-6333}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dir) DIR="$2"; shift 2 ;;
    --collection) COLLECTION="$2"; shift 2 ;;
    --qdrant) QDRANT_URL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
source "$BASE_DIR/config/paths.env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true

[[ -n "$DIR" ]] || DIR="$DATA_DIR/inbox"
mkdir -p "$DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[rag] venv not found: $VENV_DIR" >&2
  exit 2
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip -q show qdrant-client >/dev/null 2>&1 || {
  echo "[rag] deps missing. Install:" >&2
  echo "  source \"$VENV_DIR/bin/activate\" && pip install -r \"$BASE_DIR/modules/rag/requirements.txt\"" >&2
  exit 2
}

cmd=(python "$BASE_DIR/modules/rag/ingest.py" --dir "$DIR" --qdrant "$QDRANT_URL" --collection "$COLLECTION")
if [[ "$APPLY" -eq 1 ]]; then cmd+=(--apply); fi

echo "[rag] run: ${cmd[*]}"
"${cmd[@]}"
