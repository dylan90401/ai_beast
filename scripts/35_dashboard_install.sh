#!/usr/bin/env bash
set -euo pipefail
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
[[ -f "$BASE_DIR/config/paths.env" ]] || { echo "[dashboard-install] ERROR: Missing config/paths.env" >&2; exit 1; }
source "$BASE_DIR/config/paths.env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true

mkdirp(){ [[ "$APPLY" -eq 1 ]] && mkdir -p "$1" || echo "[dashboard-install] DRYRUN mkdir -p $1"; }

mkdirp "$BASE_DIR/apps/dashboard/static"
mkdirp "$BASE_DIR/config/secrets"

# Ensure port var exists
if [[ "$APPLY" -eq 1 ]]; then
  touch "$BASE_DIR/config/ports.env"
  grep -q '^export PORT_DASHBOARD=' "$BASE_DIR/config/ports.env" || echo 'export PORT_DASHBOARD="8787"' >> "$BASE_DIR/config/ports.env"
else
  echo "[dashboard-install] DRYRUN ensure PORT_DASHBOARD in config/ports.env"
fi

token="$BASE_DIR/config/secrets/dashboard_token.txt"
if [[ ! -f "$token" ]]; then
  if [[ "$APPLY" -eq 1 ]]; then
    python3 - <<'PY' > "$token"
import secrets; print(secrets.token_urlsafe(32))
PY
    chmod 600 "$token"
    echo "[dashboard-install] Created token at $token"
  else
    echo "[dashboard-install] DRYRUN create token at $token"
  fi
fi

if [[ "$APPLY" -eq 1 ]]; then
  cp -f "$BASE_DIR/apps/dashboard/_template/dashboard.py" "$BASE_DIR/apps/dashboard/dashboard.py"
  chmod 755 "$BASE_DIR/apps/dashboard/dashboard.py"
  cp -f "$BASE_DIR/apps/dashboard/_template/index.html" "$BASE_DIR/apps/dashboard/static/index.html"
  echo "[dashboard-install] Installed dashboard."
else
  echo "[dashboard-install] DRYRUN install dashboard templates."
fi
