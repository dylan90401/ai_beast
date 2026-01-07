#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true
FILE=""
KEY=""
SIG=""
PRINCIPAL=""
NAMESPACE=""
APPLY=0
VERBOSE=0

for arg in "${@:-}"; do
  case "$arg" in
    --file=*) FILE="${arg#--file=}" ;;
    --key=*) KEY="${arg#--key=}" ;;
    --sig=*) SIG="${arg#--sig=}" ;;
    --principal=*) PRINCIPAL="${arg#--principal=}" ;;
    --namespace=*) NAMESPACE="${arg#--namespace=}" ;;
    --apply) APPLY=1 ;;
    --verbose) VERBOSE=1 ;;
  esac
done

log(){ echo "[manifest] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[manifest][dbg] $*" || true; }
die(){ echo "[manifest] ERROR: $*" >&2; exit 1; }

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIGNERS_JSON="$BASE_DIR/config/resources/signers.json"

need(){ command -v "$1" >/dev/null 2>&1 || die "Missing '$1'"; }

load_signers(){
  [[ -f "$SIGNERS_JSON" ]] || die "Missing signers registry: $SIGNERS_JSON"
  local ns
  ns="$(jq -r '.namespace // "ai-beast-manifest"' "$SIGNERS_JSON")"
  [[ -n "$NAMESPACE" ]] || NAMESPACE="$ns"
  local out="$BASE_DIR/.cache/allowed_signers"
  mkdir -p "$BASE_DIR/.cache"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would build allowed signers file: $out"
    return 0
  fi
  : > "$out"
  local count
  count="$(jq '.allowed_signers | length' "$SIGNERS_JSON")"
  local i
  for ((i=0;i<count;i++)); do
    local enabled pub principals
    enabled="$(jq -r ".allowed_signers[$i].enabled // false" "$SIGNERS_JSON")"
    [[ "$enabled" == "true" ]] || continue
    pub="$(jq -r ".allowed_signers[$i].public_key" "$SIGNERS_JSON")"
    principals="$(jq -r ".allowed_signers[$i].principals[]? // empty" "$SIGNERS_JSON" | tr '\n' ' ')"
    [[ -n "$pub" ]] || continue
    for pr in $principals; do
      echo "$pr $pub" >> "$out"
    done
  done
  chmod 600 "$out" || true
  dbg "allowed_signers lines: $(wc -l < "$out" | tr -d ' ')"
}

case "$ACTION" in
  sign)
    need ssh-keygen
    [[ -n "$FILE" ]] || die "Usage: manifest sign --file=PATH [--key=~/.ssh/id_ed25519] [--principal=ai-beast-dev] [--namespace=ai-beast-manifest] [--apply]"
    [[ -f "$FILE" ]] || die "File not found: $FILE"
    [[ -n "$KEY" ]] || KEY="${AI_BEAST_SIGN_KEY:-$HOME/.ssh/id_ed25519}"
    [[ -n "$PRINCIPAL" ]] || PRINCIPAL="${AI_BEAST_SIGN_PRINCIPAL:-ai-beast-dev}"
    load_signers || true
    local_sig="${SIG:-${FILE}.sig}"
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would sign $FILE -> $local_sig (key=$KEY principal=$PRINCIPAL namespace=$NAMESPACE)"
      exit 0
    fi
    [[ -f "$KEY" ]] || die "Signing key not found: $KEY"
    log "Signing: $FILE"
    ssh-keygen -Y sign -f "$KEY" -n "$NAMESPACE" -I "$PRINCIPAL" "$FILE" >/dev/null
    # ssh-keygen writes FILE.sig by default
    [[ -f "${FILE}.sig" ]] || die "Signature not created: ${FILE}.sig"
    if [[ "$local_sig" != "${FILE}.sig" ]]; then
      mv "${FILE}.sig" "$local_sig"
    fi
    log "Wrote signature: $local_sig"
    ;;

  verify)
    need ssh-keygen
    [[ -n "$FILE" ]] || die "Usage: manifest verify --file=PATH [--sig=PATH.sig] [--namespace=ai-beast-manifest] [--apply]"
    [[ -f "$FILE" ]] || die "File not found: $FILE"
    [[ -n "$SIG" ]] || SIG="${FILE}.sig"
    [[ -f "$SIG" ]] || die "Signature not found: $SIG"
    load_signers
    local allowed="$BASE_DIR/.cache/allowed_signers"
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would verify $FILE against $SIG using $allowed (namespace=$NAMESPACE)"
      exit 0
    fi
    [[ -f "$allowed" ]] || die "Allowed signers file missing (enable at least one signer in $SIGNERS_JSON)"
    log "Verifying signature: $SIG"
    # verify reads message from stdin
    if ssh-keygen -Y verify -n "$NAMESPACE" -f "$allowed" -s "$SIG" < "$FILE" >/dev/null 2>&1; then
      log "OK: signature valid"
      exit 0
    fi
    die "Signature verification failed"
    ;;

  help|*)
    cat <<EOF
Manifest signing (optional)

Commands:
  ./bin/beast manifest sign   --file=PATH [--key=~/.ssh/id_ed25519] [--principal=ai-beast-dev] [--namespace=ai-beast-manifest] [--apply]
  ./bin/beast manifest verify --file=PATH [--sig=PATH.sig]         [--namespace=ai-beast-manifest] [--apply]

Notes:
- Uses OpenSSH ssh-keygen -Y sign/verify (ships with macOS).
- Enable at least one signer in: $SIGNERS_JSON
- Signatures are used to protect critical manifests (e.g., config/asset_packs.json).
EOF
    ;;
esac
