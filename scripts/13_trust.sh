#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true
APPLY=0
VERBOSE=0

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --verbose) VERBOSE=1 ;;
  esac
done

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY="$BASE_DIR/config/resources/trust_policy.json"
ALLOW="$BASE_DIR/config/resources/allowlists.json"
PROV_DB="$BASE_DIR/provenance/provenance.db.jsonl"
QUAR="$BASE_DIR/quarantine"

log(){ echo "[trust] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[trust][dbg] $*" || true; }
die(){ echo "[trust] ERROR: $*" >&2; exit 1; }

mkdir -p "$BASE_DIR/provenance" "$QUAR"

# basic helper: compute sha256
sha256(){
  python3 - <<PY
import hashlib,sys,pathlib
p=pathlib.Path(sys.argv[1])
h=hashlib.sha256(p.read_bytes()).hexdigest()
print(h)
PY "$1"
}

# record provenance event (append jsonl)
prov(){
  python3 - <<PY
import json, time, pathlib, os, sys
p=pathlib.Path(os.environ["PROV_DB"])
p.parent.mkdir(parents=True, exist_ok=True)
event=json.loads(sys.argv[1])
event["ts"]=time.time()
p.write_text("", encoding="utf-8") if not p.exists() else None
with p.open("a", encoding="utf-8") as f:
  f.write(json.dumps(event)+"\n")
print("[trust] provenance recorded:", event.get("type"), event.get("name",""))
PY "$1"
}

check_allowlist_models(){
  python3 - <<PY
import json, pathlib, sys, hashlib, os
base=pathlib.Path(os.environ["BASE_DIR"])
allow=json.loads(pathlib.Path(os.environ["ALLOW"]).read_text())
models_dir = base/"models"
models=allow.get("models", {}) or {}
missing=[]
bad=[]
for name, cfg in models.items():
    rel=cfg.get("path") or ""
    # allow either explicit path or name.safetensors under models/
    cand = base/rel if rel else (models_dir/f"{name}.safetensors")
    if not cand.exists():
        missing.append({"name": name, "expected": str(cand)})
        continue
    want=cfg.get("sha256","").strip()
    if want:
        got=hashlib.sha256(cand.read_bytes()).hexdigest()
        if got.lower()!=want.lower():
            bad.append({"name": name, "path": str(cand), "want": want, "got": got})
print(json.dumps({"missing": missing, "bad": bad}, indent=2))
PY
}

check_xattr_quarantine(){
  # macOS quarantine flags can be set on downloaded files; we don't auto-clear without --apply
  if ! command -v xattr >/dev/null 2>&1; then
    log "xattr not available; skipping quarantine checks"
    return 0
  fi
  local target="${1:-$BASE_DIR}"
  local found
  found="$(xattr -rl "$target" 2>/dev/null | grep -B1 -E 'com.apple.quarantine' || true)"
  if [[ -z "$found" ]]; then
    log "no com.apple.quarantine xattrs found under $target"
    return 0
  fi
  log "quarantine xattrs detected under $target"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would offer to clear quarantine xattrs"
    return 0
  fi
  log "clearing com.apple.quarantine under $target"
  xattr -r -d com.apple.quarantine "$target" || true
}

scan_containers(){
  # optional: trivy if installed
  if ! command -v trivy >/dev/null 2>&1; then
    log "trivy not installed; skipping container scan (install via: brew install trivy)"
    return 0
  fi

  ALLOW="$ALLOW" python3 - <<'PY' | while read -r img; do
import json, pathlib, os
allow=json.loads(pathlib.Path(os.environ["ALLOW"]).read_text())
containers=allow.get("containers", {}) or {}
for _,v in containers.items():
    img=v.get("image","")
    if img:
        print(img)
PY
    [[ -n "$img" ]] || continue
    log "trivy scan: $img (may take time)"
    trivy image --quiet "$img" || true
  done
}

report(){
  [[ -f "$POLICY" ]] || die "Missing policy: $POLICY"
  [[ -f "$ALLOW" ]] || die "Missing allowlists: $ALLOW"
  log "policy: $POLICY"
  log "allowlists: $ALLOW"
  echo
  log "model allowlist check:"
  BASE_DIR="$BASE_DIR" ALLOW="$ALLOW" check_allowlist_models | sed 's/^/[trust] /'
  echo
  check_xattr_quarantine "$BASE_DIR"
  echo
  scan_containers
}

case "$ACTION" in
  report|status)
    report
    ;;
  record)
    # usage: ./bin/beast trust record '{"type":"model","name":"foo","sha256":"...","source":"official"}'
    export PROV_DB
    prov "$1"
    ;;
  quarantine-check)
    check_xattr_quarantine "$BASE_DIR"
    ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast trust report [--verbose] [--apply]
  ./bin/beast trust quarantine-check [--apply]
  ./bin/beast trust record '<json-event>'

Files:
  $POLICY
  $ALLOW
  $PROV_DB

Notes:
- 'report' validates allowlisted assets when sha256 is present.
- macOS quarantine xattrs are detected; with --apply we clear them under the workspace.
- Optional: if 'trivy' is installed, container images in allowlists are scanned.
EOF
    ;;
esac
