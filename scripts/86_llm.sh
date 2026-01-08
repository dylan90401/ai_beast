#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${BASE_DIR:-$(cd "$script_dir/.." && pwd)}"
PYTHON="${PYTHON:-python3}"

JSON=0
FORCE=0
for arg in "${@:-}"; do
  [[ "$arg" == "--json" ]] && JSON=1
  [[ "$arg" == "--force" ]] && FORCE=1
done

die(){ echo "[llm] ERROR: $*" >&2; exit 1; }

run_py(){
  local code="$1"
  "$PYTHON" - "$BASE_DIR" "$JSON" "$FORCE" "$code" <<'PY'
import json
import sys
from pathlib import Path

base_dir = Path(sys.argv[1])
json_mode = sys.argv[2] == "1"
force = sys.argv[3] == "1"
action = sys.argv[4]
sys.path.insert(0, str(base_dir))

from modules.llm import LLMManager  # noqa: E402

mgr = LLMManager(base_dir)

if action == "status":
    status = {
        "ollama_running": mgr.ollama_running(),
        "storage": mgr.get_storage_info(),
    }
    if json_mode:
        print(json.dumps(status, indent=2))
    else:
        print(f"Ollama running: {status['ollama_running']}")
        for name, info in status["storage"].items():
            path = info.get("path", "n/a")
            if info.get("exists") is False:
                print(f"{name}: {path} (missing)")
                continue
            if info.get("error"):
                print(f"{name}: {path} ({info['error']})")
                continue
            print(
                f"{name}: {path} used {info['used_human']} / {info['total_human']} "
                f"({info['percent_used']}%)"
            )
elif action == "list":
    models = [m.to_dict() for m in mgr.list_all_models(force_scan=force)]
    if json_mode:
        print(json.dumps(models, indent=2))
    else:
        if not models:
            print("No models found.")
        for m in models:
            print(
                f"{m['name']}\t{m['model_type']}\t{m['location']}\t"
                f"{m['size_human']}\t{m['path']}"
            )
else:
    raise SystemExit(f"Unknown action: {action}")
PY
}

case "$ACTION" in
  status)
    run_py "status"
    ;;
  list)
    run_py "list"
    ;;
  help|--help|-h)
    cat <<'EOT'
Usage:
  ./bin/beast llm status [--json]
  ./bin/beast llm list [--json] [--force]

Notes:
- status shows Ollama health + storage info for LLM directories.
- list scans local + Ollama models; use --force to rescan disk.
EOT
    ;;
  *)
    die "Usage: beast llm {status|list|help} [--json] [--force]"
    ;;
esac
