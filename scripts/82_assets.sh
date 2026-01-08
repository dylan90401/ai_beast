#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true

APPLY=0
STRICT=0
RAG=0
TRUST_MODE="enforce"  # enforce|warn|off
QUAR_CLEAR=1
ROLLBACK_ON_FAIL=1
PACK=""
MIRROR=""
ONLY="" # models|workflows|all
YES=0

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --strict) STRICT=1 ;;
    --rag) RAG=1 ;;
    --pack=*) PACK="${arg#--pack=}" ;;
    --only=*) ONLY="${arg#--only=}" ;;
    --mirror=*) MIRROR="${arg#--mirror=}" ;;
    --trust=*) TRUST_MODE="${arg#--trust=}" ;;
    --no-quarantine-clear) QUAR_CLEAR=0 ;;
    --no-rollback) ROLLBACK_ON_FAIL=0 ;;
    --yes) YES=1 ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
MIRRORS_JSON="$BASE_DIR/config/resources/mirrors.json"
DEFAULT_MIRROR_NAME=""
if [[ -f "$MIRRORS_JSON" ]]; then
  DEFAULT_MIRROR_NAME="$(jq -r '.defaults.mirror // ""' "$MIRRORS_JSON" 2>/dev/null || echo "")"
fi

die(){ echo "[assets] ERROR: $*" >&2; exit 1; }
log(){ echo "[assets] $*"; }
need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing '$1'"; }


verify_manifest_sig(){
  local file="$1"
  local sig="${2:-${file}.sig}"

  local policy="$BASE_DIR/config/resources/trust_policy.json"
  local state="$BASE_DIR/config/state.json"
  [[ -f "$policy" ]] || return 0

  local req
  req="$(python3 - <<'PY'
import json, pathlib, os
base=pathlib.Path(os.environ["BASE_DIR"])
policy=json.loads((base/"config/resources/trust_policy.json").read_text())
state=json.loads((base/"config/state.json").read_text()) if (base/"config/state.json").exists() else {}
m=state.get("desired",{}).get("trust_modes",{}) or {}
mode=m.get("manifests","signed_optional")
mcfg=policy.get("modes",{}).get("manifests",{}).get(mode,{})
req = mcfg.get("require_signature", policy.get("defaults",{}).get("manifests",{}).get("require_signature", False))
print("1" if req else "0")
PY
)"
  [[ "$req" == "1" ]] || return 0

  if [[ ! -f "$sig" ]]; then
    if [[ "$TRUST_MODE" == "warn" || "$TRUST_MODE" == "off" ]]; then
      log "WARN: manifest signature required but missing: $sig (continuing due to trust=$TRUST_MODE)"
      return 0
    fi
    die "Manifest signature required but missing: $sig (run: ./bin/beast manifest sign --file=$file --apply)"
  fi

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would verify manifest signature: $sig"
    "$BASE_DIR/scripts/18_manifest_sign.sh" verify --file="$file" --sig="$sig" || true
    return 0
  fi

  "$BASE_DIR/scripts/18_manifest_sign.sh" verify --file="$file" --sig="$sig" --apply
}


[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

INSTALLED_FILES=()

cleanup_on_fail(){
  local rc="$1"
  if [[ "$rc" -ne 0 && "$ROLLBACK_ON_FAIL" -eq 1 && "${#INSTALLED_FILES[@]}" -gt 0 ]]; then
    log "Rollback-on-fail: removing ${#INSTALLED_FILES[@]} newly-installed files..."
    for f in "${INSTALLED_FILES[@]}"; do
      [[ -f "$f" ]] && rm -f "$f" || true
    done
  fi
}
trap 'cleanup_on_fail $?' EXIT


cfg="$BASE_DIR/config/asset_packs.json"
[[ -f "$cfg" ]] || die "Missing $cfg"

allow_models="$BASE_DIR/config/model_sources_allowlist.txt"
allow_workflows="$BASE_DIR/config/workflow_sources_allowlist.txt"

need_cmd jq
need_cmd curl
need_cmd shasum

mkdir -p "$DOWNLOAD_DIR/asset_packs" "$DATA_DIR/registry/assets" "$DATA_DIR/research/notes" "$BASE_DIR/logs"

# Determine workflows dir
default_wf_dir="$COMFYUI_DIR/workflows"
alt_wf_dir="$COMFYUI_DIR/user/default/workflows"
if [[ -d "$alt_wf_dir" ]]; then
  WF_DIR="$alt_wf_dir"
else
  WF_DIR="$default_wf_dir"
fi
mkdir -p "$WF_DIR"

# Determine models dir
[[ -n "${COMFYUI_MODELS_DIR:-}" ]] || die "COMFYUI_MODELS_DIR not set (run: ./bin/beast comfy postinstall --apply)"
mkdir -p "$COMFYUI_MODELS_DIR"

is_allowlisted(){
  local url="$1" allowfile="$2"
  [[ -f "$allowfile" ]] || return 0
  while IFS= read -r prefix; do
    [[ -z "$prefix" ]] && continue
    [[ "$url" == "$prefix"* ]] && return 0
  done < "$allowfile"
  return 1
}


trust_enforce(){
  local type="$1" name="$2" url="$3" sha="$4"
  local args=("--mode=$TRUST_MODE")
  [[ "$APPLY" -eq 1 ]] && args+=("--apply")
  "$BASE_DIR/scripts/14_trust_enforce_asset.sh" "$type" "$name" "$url" "$sha" "${args[@]}" || return $?
}

maybe_clear_quarantine(){
  local f="$1"
  [[ "$QUAR_CLEAR" -eq 1 ]] || return 0
  [[ "$APPLY" -eq 1 ]] || return 0
  command -v xattr >/dev/null 2>&1 || return 0
  # If file has com.apple.quarantine, clear it (macOS only).
  if xattr -p com.apple.quarantine "$f" >/dev/null 2>&1; then
    log "Clearing macOS quarantine xattr: $(basename "$f")"
    xattr -d com.apple.quarantine "$f" >/dev/null 2>&1 || true
  fi
}
sha256_file(){
  local f="$1"
  shasum -a 256 "$f" | awk '{print $1}'
}


resolve_mirror_url(){
  # Inputs via globals:
  #   MIRROR (dir path OR mirror name)
  #   DEFAULT_MIRROR_NAME
  #   DL_TYPE (models|loras|workflows|nodes)
  #   DL_SHA (sha256 or empty)
  #   DL_FILENAME (filename)
  #   URL (original url)
  local url="$1"
  local chosen=""
  local mirror_name=""

  # Back-compat: if MIRROR is a directory, keep old behavior (handled earlier)
  if [[ -n "${MIRROR:-}" && ! -d "$MIRROR" ]]; then
    mirror_name="$MIRROR"
  elif [[ -z "${MIRROR:-}" && -n "${DEFAULT_MIRROR_NAME:-}" ]]; then
    mirror_name="$DEFAULT_MIRROR_NAME"
  fi

  if [[ -z "$mirror_name" || ! -f "$MIRRORS_JSON" ]]; then
    DL_MIRROR_USED=""
    DL_RESOLVED_URL="$url"
    echo "$url"
    return 0
  fi

  # generate candidate urls from mirrors.json
  local candidates
  candidates="$(python3 - <<'PY'
import json, os, pathlib, sys
base=pathlib.Path(os.environ["BASE_DIR"])
mj=base/"config/resources/mirrors.json"
m=json.loads(mj.read_text())
name=os.environ.get("MIRROR_NAME","")
url=os.environ.get("ORIG_URL","")
sha=os.environ.get("DL_SHA","") or ""
fn=os.environ.get("DL_FILENAME","") or ""
typ=os.environ.get("DL_TYPE","") or ""
mir=m.get("mirrors",{}).get(name)
if not mir:
  print(url); sys.exit(0)
if mir.get("enabled") is False:
  # allow forcing by name even if disabled
  pass
types=mir.get("types") or []
# if types specified and typ not in it, skip mirror
if types and typ and typ not in types:
  print(url); sys.exit(0)
base_url=mir.get("base_url","")
cands=[]
for mode in mir.get("modes",[]):
  t=mode.get("type")
  if t=="prefix_replace":
    pf=mir.get("prefix_from","")
    pt=mir.get("prefix_to","")
    if pf and pt and url.startswith(pf):
      cands.append(url.replace(pf, pt, 1))
  else:
    tpl=mode.get("template","")
    if not tpl or not base_url:
      continue
    if not sha:
      continue
    cands.append(tpl.format(base=base_url.rstrip("/"), sha256=sha, filename=fn))
# always add original last
cands.append(url)
# print unique, order-preserving
seen=set(); out=[]
for c in cands:
  if c in seen: continue
  seen.add(c); out.append(c)
print("\\n".join(out))
PY
)"
  if [[ -z "$candidates" ]]; then
    DL_MIRROR_USED=""
    DL_RESOLVED_URL="$url"
    echo "$url"
    return 0
  fi

  # pick first alive (HEAD) when applying; otherwise first candidate
  local head_timeout="6"
  if [[ -f "$MIRRORS_JSON" ]]; then
    head_timeout="$(jq -r '.defaults.head_timeout_seconds // 6' "$MIRRORS_JSON" 2>/dev/null || echo 6)"
  fi

  if [[ "$APPLY" -ne 1 ]]; then
    chosen="$(echo "$candidates" | head -n 1)"
  else
    while IFS= read -r c; do
      [[ -n "$c" ]] || continue
      if curl -I -L --max-time "$head_timeout" --silent --fail "$c" >/dev/null 2>&1; then
        chosen="$c"; break
      fi
    done <<< "$candidates"
    [[ -n "$chosen" ]] || chosen="$url"
  fi

  DL_MIRROR_USED="$mirror_name"
  DL_RESOLVED_URL="$chosen"
  echo "$chosen"
}


download_one(){
  local url="$1" out="$2"
  # Mirror support: if --mirror=<dir> provided and file exists, copy it instead of downloading.
  if [[ -n "${MIRROR:-}" ]]; then
    local f
    f="$(basename "$out")"
    local cand1="$MIRROR/download/asset_packs/${pack:-unknown}/$f"
    local cand2="$MIRROR/asset_packs/${pack:-unknown}/$f"
    local cand3="$MIRROR/$f"
    for c in "$cand1" "$cand2" "$cand3"; do
      if [[ -f "$c" ]]; then
        if [[ "$APPLY" -ne 1 ]]; then
          log "DRYRUN: Mirror hit: would copy $c -> $out"
        else
          log "Mirror hit: $c"
          mkdir -p "$(dirname "$out")"
          cp -n "$c" "$out" || true
        fi
        return 0
      fi
    done
  fi


  local url="$1" out="$2"
  if [[ -f "$out" ]]; then
    log "Already downloaded: $(basename "$out")"
    return 0
  fi
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: curl -L --fail --retry 5 --retry-delay 2 -o "$out" "$url""
    return 0
  fi
  log "Downloading: $url"
  curl -L --fail --retry 5 --retry-delay 2 --continue-at - -o "$out.part" "$url"
  mv "$out.part" "$out"
}

maybe_clamav_scan(){
  local f="$1"
  if command -v clamscan >/dev/null 2>&1; then
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: clamscan "$f""
      return 0
    fi
    log "ClamAV scan: $(basename "$f")"
    clamscan "$f" || die "ClamAV flagged file: $f"
  else
    log "ClamAV not installed; skipping scan (enable defsec pack for scanning)."
  fi
}

write_provenance(){
  local pack="$1" kind="$2" name="$3" url="$4" sha="$5" dest="$6" note="$7" license="$8" size="$9"
  local reg_dir="$DATA_DIR/registry/assets/$pack"
  mkdir -p "$reg_dir"

  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  # JSONL manifest
  local jsonl="$reg_dir/manifest.jsonl"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would append provenance to $jsonl"
  else
    jq -nc --arg ts "$ts" --arg pack "$pack" --arg kind "$kind" --arg name "$name" --arg url "$url" --arg resolved_url "${DL_RESOLVED_URL:-$url}" --arg mirror "${DL_MIRROR_USED:-}" --arg sha "$sha" --arg dest "$dest" --arg note "$note" --arg lic "$license" --arg size "$size"       '{timestamp:$ts, pack:$pack, kind:$kind, name:$name, url:$url, resolved_url:$resolved_url, mirror:$mirror, sha256:$sha, dest:$dest, size_bytes:($size|tonumber), license:$lic, notes:$note}' >> "$jsonl"
  fi


# Global provenance DB (cross-pack, appliance-grade)
local pdb_dir="$DATA_DIR/provenance"
local pdb="$pdb_dir/provenance.db.jsonl"
if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would append to $pdb"
else
  mkdir -p "$pdb_dir"
  # stable id: pack/kind/name/url/sha/dest
  local rid
  rid="$(printf "%s" "$pack|$kind|$name|$url|$sha|$dest" | (shasum -a 256 2>/dev/null || sha256sum) | awk '{print $1}')"
  jq -nc --arg ts "$ts" --arg id "$rid" --arg pack "$pack" --arg kind "$kind" --arg name "$name" --arg url "$url" --arg resolved_url "${DL_RESOLVED_URL:-$url}" --arg mirror "${DL_MIRROR_USED:-}" --arg sha "$sha" --arg dest "$dest" --arg lic "$license" --arg note "$note" --arg sz "$size"       '{ts:$ts, id:$id, pack:$pack, kind:$kind, name:$name, url:$url, resolved_url:$resolved_url, mirror:$mirror, sha256:$sha, dest:$dest, size_bytes:($sz|tonumber), license:$lic, notes:$note}' >> "$pdb"
fi

  # Human note (append)
  local md="$reg_dir/manifest.md"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would update $md"
  else
    if [[ ! -f "$md" ]]; then
      cat > "$md" <<EOF
# Asset Pack: $pack

Generated: $ts (UTC)

## Items
EOF
    fi
    cat >> "$md" <<EOF

- **$kind**: $name  
  - URL: $url  
  - SHA256: \`$sha\`  
  - Dest: \`$dest\`  
  - Size: $size bytes  
  - License: $license  
  - Notes: $note
EOF
  fi
}

install_models_array(){
  local pack="$1" arrpath="$2"
  local count
  count="$(jq -r --arg p "$pack" "$arrpath | length" "$cfg")"
  [[ "$count" != "null" ]] || return 0
  [[ "$count" -gt 0 ]] || return 0

  for ((i=0;i<count;i++)); do
    local name kind subdir file url wantsha lic note
    name="$(jq -r --arg p "$pack" "${arrpath}[$i].name" "$cfg")"
    kind="$(jq -r --arg p "$pack" "${arrpath}[$i].kind" "$cfg")"
    subdir="$(jq -r --arg p "$pack" "${arrpath}[$i].dest_subdir" "$cfg")"
    file="$(jq -r --arg p "$pack" "${arrpath}[$i].filename" "$cfg")"
    url="$(jq -r --arg p "$pack" "${arrpath}[$i].url" "$cfg")"
    wantsha="$(jq -r --arg p "$pack" "${arrpath}[$i].sha256" "$cfg")"
    lic="$(jq -r --arg p "$pack" "${arrpath}[$i].license // \"\"" "$cfg")"
    note="$(jq -r --arg p "$pack" "${arrpath}[$i].notes // \"\"" "$cfg")"

    [[ -n "$url" && "$url" != "null" ]] || die "Missing URL for $pack/$name"
        trust_enforce "model" "$name" "$url" "$wantsha"

if [[ "$STRICT" -eq 1 ]] && ! is_allowlisted "$url" "$allow_models"; then
      die "Model URL not allowlisted (strict): $url"
    fi
    if [[ -f "$allow_models" ]] && ! is_allowlisted "$url" "$allow_models"; then
      log "WARN: model URL not allowlisted: $url"
    fi

    local dl_dir="$DOWNLOAD_DIR/asset_packs/$pack"
    mkdir -p "$dl_dir"
    local dl="$dl_dir/$file"
    download_one "$url" "$dl"

    # verify checksum if provided
    local gotsha=""
    if [[ -f "$dl" ]]; then
      maybe_clear_quarantine "$dl"

      gotsha="$(sha256_file "$dl")"
      if [[ -n "$wantsha" && "$wantsha" != "null" && "$wantsha" != "" ]]; then
        [[ "$gotsha" == "$wantsha" ]] || die "Checksum mismatch for $file (want=$wantsha got=$gotsha)"
      else
        log "No sha256 provided for $file; computed: $gotsha"
      fi
      maybe_clamav_scan "$dl"
    fi

    local dest_dir="$COMFYUI_MODELS_DIR/$subdir"
    mkdir -p "$dest_dir"
    local dest="$dest_dir/$file"

    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would install model -> $dest"
    else
      if [[ -f "$dest" ]]; then
        log "Exists: $dest"
      else
        local tmp="${dest}.__partial.$$"
        cp "$dl" "$tmp"
        mv -n "$tmp" "$dest" 2>/dev/null || rm -f "$tmp"
        [[ -f "$dest" ]] && INSTALLED_FILES+=("$dest")
      fi
    fi

    local size="0"
    [[ -f "$dl" ]] && size="$(wc -c < "$dl" | tr -d ' ')"
    write_provenance "$pack" "$kind" "$name" "$url" "${gotsha:-$wantsha}" "$dest" "$note" "$lic" "$size"
  done
}

install_workflows(){
  local pack="$1"
  local count
  count="$(jq -r --arg p "$pack" '.packs[$p].workflows | length' "$cfg" 2>/dev/null || echo 0)"
  [[ "$count" != "null" ]] || count=0
  [[ "$count" -gt 0 ]] || return 0

  local dl_dir="$DOWNLOAD_DIR/asset_packs/$pack"
  mkdir -p "$dl_dir"

  for ((i=0;i<count;i++)); do
    local name file url wantsha note
    name="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].name" "$cfg")"
    file="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].filename" "$cfg")"
    url="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].url" "$cfg")"
    wantsha="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].sha256" "$cfg")"
    note="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].notes // """ "$cfg")"

    [[ -n "$url" && "$url" != "null" ]] || die "Missing workflow URL for $pack/$name"
        trust_enforce "workflow" "$name" "$url" "$wantsha"

if [[ "$STRICT" -eq 1 ]] && ! is_allowlisted "$url" "$allow_workflows"; then
      die "Workflow URL not allowlisted (strict): $url"
    fi
    if [[ -f "$allow_workflows" ]] && ! is_allowlisted "$url" "$allow_workflows"; then
      log "WARN: workflow URL not allowlisted: $url"
    fi

    local dl="$dl_dir/$file"
    download_one "$url" "$dl"

    local gotsha=""
    if [[ -f "$dl" ]]; then
      maybe_clear_quarantine "$dl"

      gotsha="$(sha256_file "$dl")"
      if [[ -n "$wantsha" && "$wantsha" != "null" && "$wantsha" != "" ]]; then
        [[ "$gotsha" == "$wantsha" ]] || die "Checksum mismatch for workflow $file"
      else
        log "No sha256 provided for workflow $file; computed: $gotsha"
      fi
      maybe_clamav_scan "$dl"
    fi

    local dest="$WF_DIR/$file"
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would install workflow -> $dest"
    else
      if [[ -f "$dest" ]]; then
        log "Exists: $dest"
      else
        local tmp="${dest}.__partial.$$"
        cp "$dl" "$tmp"
        mv -n "$tmp" "$dest" 2>/dev/null || rm -f "$tmp"
        [[ -f "$dest" ]] && INSTALLED_FILES+=("$dest")
      fi
    fi

    local size="0"
    [[ -f "$dl" ]] && size="$(wc -c < "$dl" | tr -d ' ')"
    write_provenance "$pack" "workflow" "$name" "$url" "${gotsha:-$wantsha}" "$dest" "$note" "" "$size"
  done
}

pack_exists(){
  jq -e --arg p "$1" '.packs[$p] != null' "$cfg" >/dev/null 2>&1
}

resolve_pack_deps(){
  local want=("$@")
  local seen="$BASE_DIR/.cache/assetpacks_seen.$$"
  mkdir -p "$BASE_DIR/.cache"
  : > "$seen"
  add(){ grep -Fqx "$1" "$seen" 2>/dev/null || echo "$1" >> "$seen"; }
  has(){ grep -Fqx "$1" "$seen" 2>/dev/null; }

  visit(){
    local p="$1"
    has "$p" && return 0
    pack_exists "$p" || die "Unknown asset pack: $p"
    mapfile -t deps < <(jq -r --arg p "$p" '.packs[$p].depends_assets[]? // empty' "$cfg")
    for d in "${deps[@]}"; do visit "$d"; done
    add "$p"
  }
  for p in "${want[@]}"; do visit "$p"; done
  cat "$seen"
  rm -f "$seen" || true
}

ensure_feature_packs(){
  local apack="$1"
  mapfile -t deps < <(jq -r --arg p "$apack" '.packs[$p].depends_packs[]? // empty' "$cfg")
  [[ "${#deps[@]}" -gt 0 ]] || return 0
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would enable feature packs: ${deps[*]}"
    return 0
  fi
  "$BASE_DIR/bin/beast" packs enable "${deps[@]}" --apply || true
}

register_rag(){
  local apack="$1"
  local ok
  ok="$(jq -r --arg p "$apack" '.packs[$p].register_rag // false' "$cfg")"
  [[ "$ok" == "true" ]] || return 0
  local col
  col="$(jq -r --arg p "$apack" '.packs[$p].rag_collection // "ai_beast"' "$cfg")"

  local note="$DATA_DIR/research/notes/asset_pack_${apack}_$(date -u +%Y%m%d_%H%M%S).md"
  local reg_dir="$DATA_DIR/registry/assets/$apack"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would write RAG note: $note"
  else
    cat > "$note" <<EOF
# Asset Pack Installed: $apack

Installed at: $(date -u +"%Y-%m-%dT%H:%M:%SZ") (UTC)

Registry:
- $reg_dir/manifest.md
- $reg_dir/manifest.jsonl

Use:
- ComfyUI Workflows: $WF_DIR
- ComfyUI Models: $COMFYUI_MODELS_DIR

Provenance & checksums are stored per item in the registry.
EOF
  fi

  if [[ "$RAG" -eq 1 ]]; then
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would ingest note dir into RAG collection: $col"
    else
      "$BASE_DIR/bin/beast" rag ingest --dir "$DATA_DIR/research/notes" --collection "$col" --apply || true
    fi
  else
    log "RAG note written (or planned). To ingest: re-run with --rag"
  fi
}

gen_lockfile(){
  # Generate a reproducible lockfile from asset_packs config + downloaded/installed files.
  local out_json="$BASE_DIR/config/assets.lock.json"
  local ts; ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  # Build array of items from config
  local tmp="$BASE_DIR/.cache/assets_lock.$$"
  mkdir -p "$BASE_DIR/.cache"
  : > "$tmp"

  jq -c '.packs | to_entries[] | {pack:.key, models:(.value.models // []), loras:(.value.loras // []), workflows:(.value.workflows // [])}' "$cfg" | while read -r entry; do
    local pack; pack="$(jq -r '.pack' <<<"$entry")"
    # Models + loras
    for arr in models loras; do
      jq -c --arg pack "$pack" --arg arr "$arr" '.[$arr][]? | {pack:$pack, kind:.kind, name:.name, filename:.filename, url:.url, dest_subdir:.dest_subdir, sha256:(.sha256//"")}' <<<"$entry"         | while read -r it; do echo "$it" >> "$tmp"; done
    done
    # Workflows
    jq -c --arg pack "$pack" '.workflows[]? | {pack:$pack, kind:"workflow", name:.name, filename:.filename, url:.url, dest_subdir:"workflows", sha256:(.sha256//"")}' <<<"$entry"       | while read -r it; do echo "$it" >> "$tmp"; done
  done

  # Enrich with observed sha/size if file exists (prefer downloads)
  local out_tmp="$tmp.out"
  : > "$out_tmp"
  while read -r it; do
    local pack kind file url sub wantsha
    pack="$(jq -r '.pack' <<<"$it")"
    kind="$(jq -r '.kind' <<<"$it")"
    file="$(jq -r '.filename' <<<"$it")"
    url="$(jq -r '.url' <<<"$it")"
    sub="$(jq -r '.dest_subdir' <<<"$it")"
    wantsha="$(jq -r '.sha256' <<<"$it")"
    local dl="$DOWNLOAD_DIR/asset_packs/$pack/$file"
    local sha="$wantsha"
    local size="0"
    if [[ -f "$dl" ]]; then
      sha="$(sha256_file "$dl")"
      size="$(wc -c < "$dl" | tr -d ' ')"
    else
      # fallback to installed locations
      local inst=""
      if [[ "$kind" == "workflow" ]]; then
        inst="$WF_DIR/$file"
      else
        inst="$COMFYUI_MODELS_DIR/$sub/$file"
      fi
      if [[ -f "$inst" ]]; then
        sha="$(sha256_file "$inst")"
        size="$(wc -c < "$inst" | tr -d ' ')"
      fi
    fi
    jq -nc --arg ts "$ts" --arg pack "$pack" --arg kind "$kind" --arg name "$(jq -r '.name'<<<"$it")" --arg file "$file" --arg url "$url" --arg resolved_url "${DL_RESOLVED_URL:-$url}" --arg mirror "${DL_MIRROR_USED:-}" --arg sub "$sub" --arg sha "$sha" --arg size "$size"       '{timestamp:$ts, pack:$pack, kind:$kind, name:$name, filename:$file, url:$url, dest_subdir:$sub, sha256:$sha, size_bytes:($size|tonumber)}' >> "$out_tmp"
  done < "$tmp"

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would write $out_json"
  else
    jq -s '{generated_at: (.[0].timestamp // ""), items: .}' "$out_tmp" > "$out_json"
    log "Wrote lockfile: $out_json"
  fi

  rm -f "$tmp" "$out_tmp" 2>/dev/null || true
}

mirror_to(){
  local dest="$1"
  [[ -n "$dest" ]] || die "Usage: assets mirror --to <dir> [--apply]"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would mirror to $dest"
    return 0
  fi
  mkdir -p "$dest"/{download,comfyui,registry,config} || true
  mkdir -p "$dest/download/asset_packs" || true

  # Copy downloads
  if [[ -d "$DOWNLOAD_DIR/asset_packs" ]]; then
    rsync -a --delete "$DOWNLOAD_DIR/asset_packs/" "$dest/download/asset_packs/"
  fi

  # Copy installed models/workflows
  if [[ -d "$COMFYUI_MODELS_DIR" ]]; then
    mkdir -p "$dest/comfyui/models"
    rsync -a "$COMFYUI_MODELS_DIR/" "$dest/comfyui/models/"
  fi
  if [[ -d "$WF_DIR" ]]; then
    mkdir -p "$dest/comfyui/workflows"
    rsync -a "$WF_DIR/" "$dest/comfyui/workflows/"
  fi

  # Copy registry
  if [[ -d "$DATA_DIR/registry/assets" ]]; then
    mkdir -p "$dest/registry/assets"
    rsync -a "$DATA_DIR/registry/assets/" "$dest/registry/assets/"
  fi

  # Copy config allowlists + packs
  cp -n "$BASE_DIR/config/asset_packs.json" "$dest/config/" 2>/dev/null || true
  cp -n "$BASE_DIR/config/assets.lock.json" "$dest/config/" 2>/dev/null || true
  cp -n "$BASE_DIR/config/model_sources_allowlist.txt" "$dest/config/" 2>/dev/null || true
  cp -n "$BASE_DIR/config/workflow_sources_allowlist.txt" "$dest/config/" 2>/dev/null || true

  log "Mirror complete: $dest"
}


list_packs(){
  jq -r '.packs | to_entries[] | "\(.key)	\(.value.desc)"' "$cfg" | expand -t 22
}

show_pack(){
  local p="$1"
  jq -r --arg p "$p" '.packs[$p]' "$cfg"
}

install_asset_pack(){
  local p="$1"
  pack_exists "$p" || die "Unknown asset pack: $p"
  ensure_feature_packs "$p"

  local do_models=1 do_wf=1
  case "$ONLY" in
    ""|all) ;;
    models) do_wf=0 ;;
    workflows) do_models=0 ;;
    *) die "Unknown --only=$ONLY (use: models|workflows|all)" ;;
  esac

  log "Installing asset pack: $p"
  if [[ "$do_models" -eq 1 ]]; then
    install_models_array "$p" ".packs[\$p].models"
    install_models_array "$p" ".packs[\$p].loras"
  fi
  if [[ "$do_wf" -eq 1 ]]; then
    install_workflows "$p"
  fi
  register_rag "$p"
  log "Done: $p"
}

case "$ACTION" in
  list) list_packs ;;
  show) [[ -n "${1:-}" ]] || die "Usage: assets show <pack>"; show_pack "$1" ;;
lock)
  gen_lockfile
  ;;
mirror)
  # Usage: assets mirror --to <dir> [--apply]
  to=""
  for arg in "${@:-}"; do
    case "$arg" in
      --to=*) to="${arg#--to=}" ;;
    esac
  done
  [[ -n "$to" ]] || die "Usage: assets mirror --to <dir> [--apply]"
  mirror_to "$to"
  ;;
install)
    if [[ -z "${1:-}" && -z "$PACK" ]]; then die "Usage: assets install <pack|all> [--apply] [--strict] [--rag] [--only=models|workflows|all]"; fi
    target="${PACK:-${1:-}}"
    if [[ "$target" == "all" ]]; then
      mapfile -t names < <(jq -r '.packs | keys[]' "$cfg")
      for p in "${names[@]}"; do install_asset_pack "$p"; done
    else
      # allow multiple packs
      packs=()
      for a in "$@"; do
        [[ "$a" == "--apply" || "$a" == "--strict" || "$a" == "--rag" || "$a" == --only=* || "$a" == --pack=* || "$a" == "--yes" ]] && continue
        packs+=("$a")
      done
      if [[ "${#packs[@]}" -eq 0 ]]; then packs=("$target"); fi
      mapfile -t ordered < <(resolve_pack_deps "${packs[@]}")
      log "Asset pack order: ${ordered[*]}"
      for p in "${ordered[@]}"; do install_asset_pack "$p"; done
    fi
    ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast assets list
  ./bin/beast assets show <pack>
  ./bin/beast assets install <pack|all> [--apply] [--strict] [--rag] [--only=models|workflows|all]

Flags:
  --apply    Actually do it (default is DRYRUN)
  --strict   Enforce allowlisted source URLs
  --trust=<enforce|warn|off>   Trust policy mode (default: enforce)
  --no-quarantine-clear        Do not clear com.apple.quarantine on downloaded assets
  --no-rollback                Disable rollback-on-fail behavior (default enabled)
  --rag      After install, ingest the generated note into your RAG collection
  --only=    Install subset: models|workflows|all

Notes:
- Edit config/asset_packs.json and replace placeholder URLs + sha256.
- Provenance is written to: DATA_DIR/registry/assets/<pack>/
EOF
    ;;
esac

maybe_clamav_scan(){
  local f="$1"
  if command -v clamscan >/dev/null 2>&1; then
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: clamscan "$f""
      return 0
    fi
    log "ClamAV scan: $(basename "$f")"
    clamscan "$f" || die "ClamAV flagged file: $f"
  else
    log "ClamAV not installed; skipping scan (enable defsec pack for scanning)."
  fi
}

write_provenance(){
  local pack="$1" kind="$2" name="$3" url="$4" sha="$5" dest="$6" note="$7" license="$8" size="$9"
  local reg_dir="$DATA_DIR/registry/assets/$pack"
  mkdir -p "$reg_dir"

  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  # JSONL manifest
  local jsonl="$reg_dir/manifest.jsonl"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would append provenance to $jsonl"
  else
    jq -nc --arg ts "$ts" --arg pack "$pack" --arg kind "$kind" --arg name "$name" --arg url "$url" --arg resolved_url "${DL_RESOLVED_URL:-$url}" --arg mirror "${DL_MIRROR_USED:-}" --arg sha "$sha" --arg dest "$dest" --arg note "$note" --arg lic "$license" --arg size "$size"       '{timestamp:$ts, pack:$pack, kind:$kind, name:$name, url:$url, resolved_url:$resolved_url, mirror:$mirror, sha256:$sha, dest:$dest, size_bytes:($size|tonumber), license:$lic, notes:$note}' >> "$jsonl"
  fi

  # Human note (append)
  local md="$reg_dir/manifest.md"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would update $md"
  else
    if [[ ! -f "$md" ]]; then
      cat > "$md" <<EOF
# Asset Pack: $pack

Generated: $ts (UTC)

## Items
EOF
    fi
    cat >> "$md" <<EOF

- **$kind**: $name  
  - URL: $url  
  - SHA256: \`$sha\`  
  - Dest: \`$dest\`  
  - Size: $size bytes  
  - License: $license  
  - Notes: $note
EOF
  fi
}

install_models_array(){
  local pack="$1" arrpath="$2"
  local count
  count="$(jq -r --arg p "$pack" "$arrpath | length" "$cfg")"
  [[ "$count" != "null" ]] || return 0
  [[ "$count" -gt 0 ]] || return 0

  for ((i=0;i<count;i++)); do
    local name kind subdir file url wantsha lic note
    name="$(jq -r --arg p "$pack" "${arrpath}[$i].name" "$cfg")"
    kind="$(jq -r --arg p "$pack" "${arrpath}[$i].kind" "$cfg")"
    subdir="$(jq -r --arg p "$pack" "${arrpath}[$i].dest_subdir" "$cfg")"
    file="$(jq -r --arg p "$pack" "${arrpath}[$i].filename" "$cfg")"
    url="$(jq -r --arg p "$pack" "${arrpath}[$i].url" "$cfg")"
    wantsha="$(jq -r --arg p "$pack" "${arrpath}[$i].sha256" "$cfg")"
    lic="$(jq -r --arg p "$pack" "${arrpath}[$i].license // \"\"" "$cfg")"
    note="$(jq -r --arg p "$pack" "${arrpath}[$i].notes // \"\"" "$cfg")"

    [[ -n "$url" && "$url" != "null" ]] || die "Missing URL for $pack/$name"
    if [[ "$STRICT" -eq 1 ]] && ! is_allowlisted "$url" "$allow_models"; then
      die "Model URL not allowlisted (strict): $url"
    fi
    if [[ -f "$allow_models" ]] && ! is_allowlisted "$url" "$allow_models"; then
      log "WARN: model URL not allowlisted: $url"
    fi

    local dl_dir="$DOWNLOAD_DIR/asset_packs/$pack"
    mkdir -p "$dl_dir"
    local dl="$dl_dir/$file"
    download_one "$url" "$dl"

    # verify checksum if provided
    local gotsha=""
    if [[ -f "$dl" ]]; then
      gotsha="$(sha256_file "$dl")"
      if [[ -n "$wantsha" && "$wantsha" != "null" && "$wantsha" != "" ]]; then
        [[ "$gotsha" == "$wantsha" ]] || die "Checksum mismatch for $file (want=$wantsha got=$gotsha)"
      else
        log "No sha256 provided for $file; computed: $gotsha"
      fi
      maybe_clamav_scan "$dl"
    fi

    local dest_dir="$COMFYUI_MODELS_DIR/$subdir"
    mkdir -p "$dest_dir"
    local dest="$dest_dir/$file"

    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would install model -> $dest"
    else
      if [[ -f "$dest" ]]; then
        log "Exists: $dest"
      else
        local tmp="${dest}.__partial.$$"
        cp "$dl" "$tmp"
        mv -n "$tmp" "$dest" 2>/dev/null || rm -f "$tmp"
        [[ -f "$dest" ]] && INSTALLED_FILES+=("$dest")
      fi
    fi

    local size="0"
    [[ -f "$dl" ]] && size="$(wc -c < "$dl" | tr -d ' ')"
    write_provenance "$pack" "$kind" "$name" "$url" "${gotsha:-$wantsha}" "$dest" "$note" "$lic" "$size"
  done
}

install_workflows(){
  local pack="$1"
  local count
  count="$(jq -r --arg p "$pack" '.packs[$p].workflows | length' "$cfg" 2>/dev/null || echo 0)"
  [[ "$count" != "null" ]] || count=0
  [[ "$count" -gt 0 ]] || return 0

  local dl_dir="$DOWNLOAD_DIR/asset_packs/$pack"
  mkdir -p "$dl_dir"

  for ((i=0;i<count;i++)); do
    local name file url wantsha note
    name="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].name" "$cfg")"
    file="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].filename" "$cfg")"
    url="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].url" "$cfg")"
    wantsha="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].sha256" "$cfg")"
    note="$(jq -r --arg p "$pack" ".packs[$p].workflows[$i].notes // """ "$cfg")"

    [[ -n "$url" && "$url" != "null" ]] || die "Missing workflow URL for $pack/$name"
    if [[ "$STRICT" -eq 1 ]] && ! is_allowlisted "$url" "$allow_workflows"; then
      die "Workflow URL not allowlisted (strict): $url"
    fi
    if [[ -f "$allow_workflows" ]] && ! is_allowlisted "$url" "$allow_workflows"; then
      log "WARN: workflow URL not allowlisted: $url"
    fi

    local dl="$dl_dir/$file"
    download_one "$url" "$dl"

    local gotsha=""
    if [[ -f "$dl" ]]; then
      gotsha="$(sha256_file "$dl")"
      if [[ -n "$wantsha" && "$wantsha" != "null" && "$wantsha" != "" ]]; then
        [[ "$gotsha" == "$wantsha" ]] || die "Checksum mismatch for workflow $file"
      else
        log "No sha256 provided for workflow $file; computed: $gotsha"
      fi
      maybe_clamav_scan "$dl"
    fi

    local dest="$WF_DIR/$file"
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would install workflow -> $dest"
    else
      if [[ -f "$dest" ]]; then
        log "Exists: $dest"
      else
        local tmp="${dest}.__partial.$$"
        cp "$dl" "$tmp"
        mv -n "$tmp" "$dest" 2>/dev/null || rm -f "$tmp"
        [[ -f "$dest" ]] && INSTALLED_FILES+=("$dest")
      fi
    fi

    local size="0"
    [[ -f "$dl" ]] && size="$(wc -c < "$dl" | tr -d ' ')"
    write_provenance "$pack" "workflow" "$name" "$url" "${gotsha:-$wantsha}" "$dest" "$note" "" "$size"
  done
}

pack_exists(){
  jq -e --arg p "$1" '.packs[$p] != null' "$cfg" >/dev/null 2>&1
}

resolve_pack_deps(){
  local want=("$@")
  local seen="$BASE_DIR/.cache/assetpacks_seen.$$"
  mkdir -p "$BASE_DIR/.cache"
  : > "$seen"
  add(){ grep -Fqx "$1" "$seen" 2>/dev/null || echo "$1" >> "$seen"; }
  has(){ grep -Fqx "$1" "$seen" 2>/dev/null; }

  visit(){
    local p="$1"
    has "$p" && return 0
    pack_exists "$p" || die "Unknown asset pack: $p"
    mapfile -t deps < <(jq -r --arg p "$p" '.packs[$p].depends_assets[]? // empty' "$cfg")
    for d in "${deps[@]}"; do visit "$d"; done
    add "$p"
  }
  for p in "${want[@]}"; do visit "$p"; done
  cat "$seen"
  rm -f "$seen" || true
}

ensure_feature_packs(){
  local apack="$1"
  mapfile -t deps < <(jq -r --arg p "$apack" '.packs[$p].depends_packs[]? // empty' "$cfg")
  [[ "${#deps[@]}" -gt 0 ]] || return 0
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would enable feature packs: ${deps[*]}"
    return 0
  fi
  "$BASE_DIR/bin/beast" packs enable "${deps[@]}" --apply || true
}

register_rag(){
  local apack="$1"
  local ok
  ok="$(jq -r --arg p "$apack" '.packs[$p].register_rag // false' "$cfg")"
  [[ "$ok" == "true" ]] || return 0
  local col
  col="$(jq -r --arg p "$apack" '.packs[$p].rag_collection // "ai_beast"' "$cfg")"

  local note="$DATA_DIR/research/notes/asset_pack_${apack}_$(date -u +%Y%m%d_%H%M%S).md"
  local reg_dir="$DATA_DIR/registry/assets/$apack"
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would write RAG note: $note"
  else
    cat > "$note" <<EOF
# Asset Pack Installed: $apack

Installed at: $(date -u +"%Y-%m-%dT%H:%M:%SZ") (UTC)

Registry:
- $reg_dir/manifest.md
- $reg_dir/manifest.jsonl

Use:
- ComfyUI Workflows: $WF_DIR
- ComfyUI Models: $COMFYUI_MODELS_DIR

Provenance & checksums are stored per item in the registry.
EOF
  fi

  if [[ "$RAG" -eq 1 ]]; then
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would ingest note dir into RAG collection: $col"
    else
      "$BASE_DIR/bin/beast" rag ingest --dir "$DATA_DIR/research/notes" --collection "$col" --apply || true
    fi
  else
    log "RAG note written (or planned). To ingest: re-run with --rag"
  fi
}

