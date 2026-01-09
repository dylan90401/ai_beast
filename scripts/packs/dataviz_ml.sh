#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"
source "$BASE_DIR/config/paths.env"
mkdir -p "$DATA_DIR/notebooks" "$DATA_DIR/datasets"
if [[ "$APPLY" -ne 1 ]]; then
  echo "[pack:dataviz_ml] DRYRUN would create notebooks dir: $DATA_DIR/notebooks"
  exit 0
fi
cat > "$DATA_DIR/notebooks/README.txt" <<EOF
Dataviz/ML pack:
Start JupyterLab:
  source "$BASE_DIR/.venv_packs/dataviz_ml/bin/activate"
  jupyter lab --notebook-dir "$DATA_DIR/notebooks"
EOF
