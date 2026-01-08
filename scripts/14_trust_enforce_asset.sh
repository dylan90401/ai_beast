#!/usr/bin/env bash
set -euo pipefail

TYPE="${1:-}"; NAME="${2:-}"; URL="${3:-}"; SHA="${4:-}"
shift 4 || true

MODE="enforce"   # enforce|warn|off
VERBOSE=0

for arg in "${@:-}"; do
  case "$arg" in
    --mode=*) MODE="${arg#--mode=}" ;;
    --verbose) VERBOSE=1 ;;
  esac
done

log(){ echo "[trust-enforce] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[trust-enforce][dbg] $*" || true; }
die(){ echo "[trust-enforce] ERROR: $*" >&2; exit 1; }

[[ -n "$TYPE" && -n "$NAME" && -n "$URL" ]] || die "Usage: $0 <model|workflow|node> <name> <url> <sha-or-empty> [--mode=enforce|warn|off] [--apply]"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
POLICY="$BASE_DIR/config/resources/trust_policy.json"
ALLOW="$BASE_DIR/config/resources/allowlists.json"

[[ -f "$POLICY" ]] || die "Missing trust policy: $POLICY"
[[ -f "$ALLOW" ]] || die "Missing allowlists: $ALLOW"

py(){
  python3 - "$@" <<'PY'
import json, re, sys, pathlib, os

type_=sys.argv[1]
name=sys.argv[2]
url=sys.argv[3]
sha=sys.argv[4] if len(sys.argv)>4 else ""
mode=os.environ.get("MODE","enforce")
policy=json.loads(pathlib.Path(os.environ["POLICY"]).read_text())
allow=json.loads(pathlib.Path(os.environ["ALLOW"]).read_text())

# Optional mode overrides from config/state.json (typed trust modes)
base=pathlib.Path(os.environ.get("BASE_DIR","."))
state_path=base/"config/state.json"
modes={}
if state_path.exists():
    try:
        st=json.loads(state_path.read_text())
        modes = (st.get("desired",{}) or {}).get("trust_modes",{}) or {}
    except Exception:
        modes={}
def apply_mode(group:str, mode_name:str):
    mcfg = (policy.get("modes",{}) or {}).get(group,{}).get(mode_name) or {}
    if not mcfg:
        return
    # override defaults for this group
    policy.setdefault("defaults",{}).setdefault(group,{})
    for k,v in mcfg.items():
        policy["defaults"][group][k]=v
# Map type_ -> group
group = "nodes" if type_ in ("nodes","custom_nodes","comfy_nodes") else ("models" if type_ in ("models","loras","checkpoints","vae") else "")
if group:
    mode_name = modes.get(group, "")
    if mode_name:
        apply_mode(group, mode_name)
# manifest signature mode handled elsewhere (asset installer)

def norm(s:str)->str:
    s=s.strip()
    s=re.sub(r'[^A-Za-z0-9]+','_',s).strip('_').lower()
    return s

def classify_url(url:str)->str:
    # default
    source="community"
    for rule in policy.get("url_classifiers", []):
        m=rule.get("match","")
        if m and url.startswith(m):
            source=rule.get("source","community")
            break
    return source

def lookup_allow(type_, name):
    bucket = allow.get(type_+"s") or allow.get(type_) or {}
    # try exact, normalized, and common variants
    keys=[name, name.upper(), name.lower(), norm(name)]
    for k in keys:
        if k in bucket:
            return bucket[k]
    # try match by normalized key
    n=norm(name)
    for k,v in bucket.items():
        if norm(k)==n:
            return v
    return None

defaults = policy.get("defaults", {})
tkey = {"model":"models","workflow":"workflows","node":"nodes"}.get(type_, type_+"s")
d = defaults.get(tkey, {})
tier_required = d.get("tier_required","community")
require_sha = bool(d.get("require_sha256", False))
require_prov = bool(d.get("require_provenance", False))

entry = lookup_allow(type_, name)
source = entry.get("source") if isinstance(entry, dict) and entry.get("source") else classify_url(url)
tier   = entry.get("tier") if isinstance(entry, dict) and entry.get("tier") else "community"

tiers = policy.get("tiers", {})
allowed_sources = tiers.get(tier_required, {}).get("min_sources", ["any"])
# Interpret "any" as allow everything
source_ok = ("any" in allowed_sources) or (source in allowed_sources)

result = {
  "type": type_,
  "name": name,
  "url": url,
  "sha_present": bool(sha and sha != "null"),
  "source": source,
  "tier": tier,
  "tier_required": tier_required,
  "allowed_sources": allowed_sources,
  "require_sha256": require_sha,
  "require_provenance": require_prov,
  "source_ok": source_ok,
  "ok": True,
  "violations": [],
  "mode": mode,
}

if not source_ok:
    result["ok"]=False
    result["violations"].append(f"source '{source}' not allowed for required tier '{tier_required}'")

if require_sha and not result["sha_present"]:
    result["ok"]=False
    result["violations"].append("sha256 required but missing")

# provenance is enforced by installer writing provenance; we just signal expectation
print(json.dumps(result))
PY
}

export MODE POLICY ALLOW
out="$(py "$TYPE" "$NAME" "$URL" "$SHA")"
dbg "$out"

ok="$(echo "$out" | python3 -c 'import json,sys; print("1" if json.load(sys.stdin)["ok"] else "0")')"
viol="$(echo "$out" | python3 -c 'import json,sys; j=json.load(sys.stdin); print("; ".join(j.get("violations",[])))')"

if [[ "$MODE" == "off" ]]; then
  log "mode=off: skipping trust enforcement for $TYPE:$NAME"
  exit 0
fi

if [[ "$ok" == "1" ]]; then
  log "PASS $TYPE:$NAME (tier_required ok)"
  exit 0
fi

if [[ "$MODE" == "warn" ]]; then
  log "WARN $TYPE:$NAME -> $viol"
  exit 0
fi

die "FAIL $TYPE:$NAME -> $viol"
