#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true
NAME="${1:-}"; shift || true

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEYCHAIN_SERVICE="${AI_BEAST_KEYCHAIN_SERVICE:-ai.beast}"
ENV_OUT="${AI_BEAST_ENV_RENDERED:-$BASE_DIR/config/secrets.rendered.env}"

die(){ echo "[secret] ERROR: $*" >&2; exit 1; }
log(){ echo "[secret] $*"; }

require_security(){
  command -v security >/dev/null 2>&1 || die "macOS 'security' tool not found (this command is macOS-only)."
}

set_secret(){
  [[ -n "$NAME" ]] || die "secret name required"
  require_security
  # read secret from stdin to avoid shell history
  local secret
  secret="$(cat)"
  [[ -n "$secret" ]] || die "empty secret"
  # -U updates if exists
  security add-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -D "ai.beast.secret" -l "$NAME" -w "$secret" -U >/dev/null
  log "stored: $NAME (Keychain service=$KEYCHAIN_SERVICE)"
}

get_secret(){
  [[ -n "$NAME" ]] || die "secret name required"
  require_security
  security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -l "$NAME" -w 2>/dev/null || die "not found: $NAME"
}

del_secret(){
  [[ -n "$NAME" ]] || die "secret name required"
  require_security
  security delete-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -l "$NAME" >/dev/null || die "not found: $NAME"
  log "deleted: $NAME"
}

list_secrets(){
  require_security
  # list labels for this service (does not reveal values)
  security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" 2>/dev/null | awk -F'"' '/"labl"<</{getline; gsub(/^[ \t]+|[\r\n]+$/,"",$2); print $2}' | sort -u || true
}

render_env(){
  require_security
  mkdir -p "$(dirname "$ENV_OUT")"
  : > "$ENV_OUT"
  chmod 600 "$ENV_OUT"
  while read -r name; do
    [[ -n "$name" ]] || continue
    val="$(security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -l "$name" -w 2>/dev/null || true)"
    [[ -n "$val" ]] || continue
    # Render as NAME=... with safe escaping for newlines
    printf '%s=%q\n' "$name" "$val" >> "$ENV_OUT"
  done < <(list_secrets)
  log "rendered: $ENV_OUT"
  log "tip: source it in your shell:  set -a; source "$ENV_OUT"; set +a"
}

case "$ACTION" in
  set)
    # usage: echo -n "value" | ./bin/beast secret set NAME
    set_secret
    ;;
  get)
    get_secret
    ;;
  del|delete|rm)
    del_secret
    ;;
  list)
    list_secrets
    ;;
  render-env)
    render_env
    ;;
  *)
    cat <<EOF
Usage:
  echo -n "VALUE" | ./bin/beast secret set <NAME>
  ./bin/beast secret get <NAME>
  ./bin/beast secret del <NAME>
  ./bin/beast secret list
  ./bin/beast secret render-env   # writes config/secrets.rendered.env (chmod 600)

Env:
  AI_BEAST_KEYCHAIN_SERVICE   default: ai.beast
  AI_BEAST_ENV_RENDERED       default: <BASE>/config/secrets.rendered.env

Notes:
- Values are stored in macOS Keychain. This command never prints values except for 'get'.
- Prefer using compose 'env_file' pointing at secrets.rendered.env for portability (file is re-renderable).
EOF
    ;;
esac
