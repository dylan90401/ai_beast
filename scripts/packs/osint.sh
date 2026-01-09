#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"
mkdir -p "$DATA_DIR/osint/inbox" "$DATA_DIR/osint/out" "$BASE_DIR/logs"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:osint] DRYRUN would create $DATA_DIR/osint/*"
  exit 0
fi
cat > "$DATA_DIR/osint/README.txt" <<EOF
OSINT pack notes:
- Use lawful sources and permissions.
- Drop text/notes into: $DATA_DIR/osint/inbox
- Optionally ingest into RAG: ./bin/beast rag ingest --dir "$DATA_DIR/osint/inbox" --apply
EOF
