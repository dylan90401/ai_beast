#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[agent] creating venv at apps/agent/.venv"
python3 -m venv "$BASE_DIR/apps/agent/.venv"

# shellcheck disable=SC1091
source "$BASE_DIR/apps/agent/.venv/bin/activate"

echo "[agent] installing requirements"
pip3 install --upgrade pip
pip3 install -r "$BASE_DIR/apps/agent/requirements.txt"

echo "[agent] done"
echo "Next:"
echo "  source apps/agent/.venv/bin/activate"
echo '  python3 apps/agent/kryptos_agent.py "Run ./bin/beast preflight and summarize"'
