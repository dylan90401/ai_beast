#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"

mkdir -p "$DATA_DIR/research/hegel" "$DATA_DIR/research/esoterica" "$DATA_DIR/research/notes" "$DATA_DIR/research/inbox"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:research] DRYRUN would create research corpus dirs under $DATA_DIR/research"
  exit 0
fi

cat > "$DATA_DIR/research/README.txt" <<EOF
Research pack:
- Put PDFs/text into: $DATA_DIR/research/inbox
- Optionally ingest into RAG:
    ./bin/beast rag ingest --dir "$DATA_DIR/research/inbox" --apply

Suggested workflow:
1) Collect sources (public domain for Hegel; annotated notes for esoterica)
2) Normalize to text/markdown where possible
3) Ingest and query through Open WebUI (RAG) or your own scripts
EOF
