#!/usr/bin/env bash
set -euo pipefail

APPLY=0
UNLOAD=0
for arg in "${@:-}"; do
  [[ "$arg" == "--apply" ]] && APPLY=1
  [[ "$arg" == "--unload" ]] && UNLOAD=1
done

die(){ echo "[launchd] ERROR: $*" >&2; exit 1; }
log(){ echo "[launchd] $*"; }

[[ "$(uname -s)" == "Darwin" ]] || die "launchd is macOS only."
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env"
source "$BASE_DIR/config/paths.env"
[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true
[[ -f "$BASE_DIR/config/ai-beast.env" ]] && source "$BASE_DIR/config/ai-beast.env" || true

mkdir -p "$BASE_DIR/logs"
agents="$HOME/Library/LaunchAgents"
mkdir -p "$agents"

label_comfy="com.aibeast.comfyui"
label_dash="com.aibeast.dashboard"
comfy_plist="$agents/$label_comfy.plist"
dash_plist="$agents/$label_dash.plist"

if [[ "$UNLOAD" -eq 1 ]]; then
  log "Unloading..."
  [[ "$APPLY" -eq 1 ]] && launchctl unload "$comfy_plist" 2>/dev/null || true
  [[ "$APPLY" -eq 1 ]] && launchctl unload "$dash_plist" 2>/dev/null || true
  log "Done."
  exit 0
fi

bind="${AI_BEAST_BIND_ADDR:-127.0.0.1}"
cport="${PORT_COMFYUI:-8188}"

if [[ "$APPLY" -eq 1 ]]; then
  cat > "$comfy_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>${label_comfy}</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>-lc</string>
      <string>source "${VENV_DIR}/bin/activate" &amp;&amp; cd "${COMFYUI_DIR}" &amp;&amp; python main.py --listen ${bind} --port ${cport}</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>${BASE_DIR}/logs/${label_comfy}.out.log</string>
    <key>StandardErrorPath</key><string>${BASE_DIR}/logs/${label_comfy}.err.log</string>
  </dict>
</plist>
EOF

  cat > "$dash_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>${label_dash}</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>-lc</string>
      <string>cd "${BASE_DIR}" &amp;&amp; python3 "${BASE_DIR}/apps/dashboard/dashboard.py"</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>${BASE_DIR}/logs/${label_dash}.out.log</string>
    <key>StandardErrorPath</key><string>${BASE_DIR}/logs/${label_dash}.err.log</string>
  </dict>
</plist>
EOF

  launchctl unload "$comfy_plist" 2>/dev/null || true
  launchctl unload "$dash_plist" 2>/dev/null || true
  launchctl load "$comfy_plist"
  launchctl load "$dash_plist"
  log "Loaded LaunchAgents. (To unload: ./bin/beast launchd --unload --apply)"
else
  log "DRYRUN would write plists to $agents and load them."
fi
