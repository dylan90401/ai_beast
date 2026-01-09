#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true
APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[speech] $*"; }
die(){ echo "[speech] ERROR: $*" >&2; exit 1; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

[[ -f "$BASE_DIR/config/ports.env" ]] && source "$BASE_DIR/config/ports.env" || true
PORT="${PORT_SPEECH_API:-9977}"
HOST="${SPEECH_HOST:-127.0.0.1}"

venv="$BASE_DIR/.venv_packs/speech_stack"
server_py="$BASE_DIR/apps/speech_api/server.py"
run_dir="$BASE_DIR/run"
pidfile="$run_dir/speech_api.pid"
mkdir -p "$run_dir" "$LOG_DIR"

is_running(){
  [[ -f "$pidfile" ]] || return 1
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

start_bg(){
  [[ -d "$venv" ]] || die "Speech pack venv missing: $venv (run: ./bin/beast packs install speech_stack --apply)"
  [[ -f "$server_py" ]] || die "Missing server: $server_py (run pack hook via packs install)"
  if is_running; then log "Already running (pid $(cat "$pidfile"))"; return 0; fi

  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  nohup python3 -m uvicorn apps.speech_api.server:app --app-dir "$BASE_DIR" --host "$HOST" --port "$PORT"     > "$LOG_DIR/speech_api.out.log" 2> "$LOG_DIR/speech_api.err.log" &
  echo $! > "$pidfile"
  deactivate || true
  log "Started Speech API (pid $(cat "$pidfile")) at http://$HOST:$PORT"
}

stop_bg(){
  if ! is_running; then log "Not running"; rm -f "$pidfile" 2>/dev/null || true; return 0; fi
  pid="$(cat "$pidfile")"
  kill "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pidfile" 2>/dev/null || true
  log "Stopped Speech API"
}

status(){
  if is_running; then
    log "running (pid $(cat "$pidfile")) -> http://$HOST:$PORT/health"
  else
    log "stopped"
  fi
}

launchd_install(){
  [[ "$(uname -s)" == "Darwin" ]] || die "launchd install is macOS only."
  agents="$HOME/Library/LaunchAgents"
  mkdir -p "$agents"

  label="com.kryptos.aibeast.speech"
  plist="$agents/$label.plist"

  [[ -d "$venv" ]] || die "Speech pack venv missing: $venv (install the pack first)"

  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>${label}</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>-lc</string>
      <string>cd "${BASE_DIR}" &amp;&amp; source "${venv}/bin/activate" &amp;&amp; exec python3 -m uvicorn apps.speech_api.server:app --app-dir "${BASE_DIR}" --host "${HOST}" --port "${PORT}"</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>${LOG_DIR}/${label}.out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/${label}.err.log</string>
  </dict>
</plist>
EOF

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would write $plist and load it via launchctl"
    return 0
  fi

  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  log "Installed + loaded LaunchAgent: $label"
}

launchd_uninstall(){
  [[ "$(uname -s)" == "Darwin" ]] || die "launchd uninstall is macOS only."
  agents="$HOME/Library/LaunchAgents"
  label="com.kryptos.aibeast.speech"
  plist="$agents/$label.plist"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would unload + remove $plist"
    return 0
  fi
  launchctl unload "$plist" 2>/dev/null || true
  rm -f "$plist" 2>/dev/null || true
  log "Uninstalled LaunchAgent: $label"
}

case "$ACTION" in
  up|start) start_bg ;;
  down|stop) stop_bg ;;
  restart) stop_bg; start_bg ;;
  status) status ;;
  logs)
    echo "== out =="; tail -n 80 "$LOG_DIR/speech_api.out.log" 2>/dev/null || true
    echo
    echo "== err =="; tail -n 80 "$LOG_DIR/speech_api.err.log" 2>/dev/null || true
    ;;
  launchd-install) launchd_install ;;
  launchd-uninstall) launchd_uninstall ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast packs install speech_stack --apply
  ./bin/beast speech up
  ./bin/beast speech status
  ./bin/beast speech down

Optional launchd (auto-start at login):
  ./bin/beast speech launchd-install --apply
  ./bin/beast speech launchd-uninstall --apply

Endpoints:
  GET  /health
  POST /transcribe  (multipart: file=@audio.wav, backend=auto|faster_whisper|whisper_cpp)
  POST /tts         (multipart: text=..., voice=..., fmt=wav|aiff)

Notes:
- Default backend: faster-whisper (CPU) for simplicity.
- whisper.cpp is built for Metal-friendly local runs; set:
    export WHISPER_CPP_BIN="\$GUTS_DIR/apps/whispercpp/whisper.cpp/main"
    export WHISPER_CPP_MODEL="\$MODELS_DIR/speech/whispercpp/<model>"
    export SPEECH_BACKEND="whisper_cpp"
EOF
    ;;
esac
