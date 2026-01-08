#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true

APPLY=0
FORCE=0
STATE_FILE=""
VERBOSE=0

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --force) FORCE=1 ;;
    --verbose) VERBOSE=1 ;;
    --state=*) STATE_FILE="${arg#--state=}" ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

log(){ echo "[state] $*"; }
dbg(){ [[ "$VERBOSE" -eq 1 ]] && echo "[state][dbg] $*" || true; }
die(){ echo "[state] ERROR: $*" >&2; exit 1; }
need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing '$1'"; }
run(){
  if [[ "$APPLY" -ne 1 ]]; then
    printf '[state] DRYRUN:'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

need_cmd jq
need_cmd python3

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

# best-effort
source "$BASE_DIR/config/features.env" 2>/dev/null || true

STATE_FILE="${STATE_FILE:-$BASE_DIR/config/state.json}"
[[ -f "$STATE_FILE" ]] || die "State file not found: $STATE_FILE"

cache="$BASE_DIR/.cache"
mkdir -p "$cache"
plan_json="$cache/state.plan.json"
plan_md="$cache/state.plan.md"

# -------------------------
# Discover actual state
# -------------------------
actual_packs(){
  # enabled packs are exported into config/features.env as FEATURE_PACKS_<name>=true|false
  if [[ ! -f "$BASE_DIR/config/features.env" ]]; then return 0; fi
  grep -E 'FEATURE_PACKS_' "$BASE_DIR/config/features.env" | while IFS='=' read -r k v; do
    k="${k#export }"
    name="${k#FEATURE_PACKS_}"
    name="${name,,}"
    v="${v,,}"
    if [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "on" ]]; then
      echo "$name"
    fi
  done | sort -u
}

actual_extensions(){
  local ext="$BASE_DIR/extensions"
  [[ -d "$ext" ]] || return 0
  find "$ext" -mindepth 2 -maxdepth 3 -type f -name enabled -print 2>/dev/null | while read -r f; do
    basename "$(dirname "$f")"
  done | sort -u
}

actual_assets_installed(){
  # heuristic: registry exists and has manifest.jsonl
  local reg="$DATA_DIR/registry/assets"
  [[ -d "$reg" ]] || return 0
  find "$reg" -mindepth 2 -maxdepth 2 -type f -name manifest.jsonl -print 2>/dev/null     | while read -r f; do
        pack="$(basename "$(dirname "$f")")"
        # has at least 1 line?
        if [[ -s "$f" ]]; then echo "$pack"; fi
      done | sort -u
}

# -------------------------
# Desired state
# -------------------------
desired_packs(){
  jq -r '.desired.packs_enabled[]? // empty' "$STATE_FILE" | sort -u
}
desired_extensions(){
  jq -r '.desired.extensions_enabled[]? // empty' "$STATE_FILE" | sort -u
}
desired_asset_specs(){
  # emits compact json objects
  jq -c '.desired.asset_packs[]? // empty' "$STATE_FILE"
}

opt_compose_regen(){ jq -r '.runtime.compose_regen // true' "$STATE_FILE"; }
opt_compose_up(){ jq -r '.runtime.compose_up // true' "$STATE_FILE"; }
opt_remove_orphans(){ jq -r '.runtime.remove_orphans // true' "$STATE_FILE"; }
opt_mirror(){ jq -r '.options.mirror // ""' "$STATE_FILE"; }
opt_strict_default(){ jq -r '.options.strict_url_allowlist_default // true' "$STATE_FILE"; }

# -------------------------
# Diff helpers
# -------------------------
setdiff(){
  # usage: setdiff <A_file> <B_file> => A\B
  comm -23 "$1" "$2" || true
}

write_plan(){
  local tmpA="$cache/actual_packs.txt"
  local tmpD="$cache/desired_packs.txt"
  local tmpAE="$cache/actual_ext.txt"
  local tmpDE="$cache/desired_ext.txt"
  local tmpAA="$cache/actual_assets.txt"

  actual_packs > "$tmpA"
  desired_packs > "$tmpD"
  actual_extensions > "$tmpAE"
  desired_extensions > "$tmpDE"
  actual_assets_installed > "$tmpAA"

  packs_enable="$(setdiff "$tmpD" "$tmpA" | jq -Rsc 'split("\n")|map(select(length>0))')"
  packs_disable="$(setdiff "$tmpA" "$tmpD" | jq -Rsc 'split("\n")|map(select(length>0))')"

  exts_enable="$(setdiff "$tmpDE" "$tmpAE" | jq -Rsc 'split("\n")|map(select(length>0))')"
  exts_disable="$(setdiff "$tmpAE" "$tmpDE" | jq -Rsc 'split("\n")|map(select(length>0))')"

  # asset: install if not in actual assets set
  assets_need="[]"
  while read -r spec; do
    [[ -z "$spec" ]] && continue
    p="$(jq -r '.pack' <<<"$spec")"
    if ! grep -Fqx "$p" "$tmpAA" 2>/dev/null; then
      assets_need="$(jq -c --argjson add "$spec" '. + [$add]' <<<"$assets_need")"
    fi
  done < <(desired_asset_specs)

  regen="$(opt_compose_regen)"
  up="$(opt_compose_up)"
  rmorph="$(opt_remove_orphans)"
  mirror="$(opt_mirror)"
  strict_default="$(opt_strict_default)"

  jq -nc     --arg state_file "$STATE_FILE"     --arg generated "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"     --argjson packs_enable "$packs_enable"     --argjson packs_disable "$packs_disable"     --argjson exts_enable "$exts_enable"     --argjson exts_disable "$exts_disable"     --argjson assets_install "$assets_need"     --arg regen "$regen" --arg up "$up" --arg rmorph "$rmorph"     --arg mirror "$mirror" --arg strict_default "$strict_default"     '{
      generated_at: $generated,
      state_file: $state_file,
      diff: {
        packs_enable: $packs_enable,
        packs_disable: $packs_disable,
        extensions_enable: $exts_enable,
        extensions_disable: $exts_disable,
        assets_install: $assets_install
      },
      runtime: {
        compose_regen: ($regen=="true"),
        compose_up: ($up=="true"),
        remove_orphans: ($rmorph=="true")
      },
      options: {
        mirror: $mirror,
        strict_url_allowlist_default: ($strict_default=="true")
      }
    }' > "$plan_json"

  # Render plan.md
  {
    echo "# AI Beast State Plan"
    echo
    echo "- Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "- State file: $STATE_FILE"
    echo
    echo "## Packs"
    echo "- Enable: $(jq -r '.diff.packs_enable|join(", ")' "$plan_json")"
    echo "- Disable: $(jq -r '.diff.packs_disable|join(", ")' "$plan_json")"
    echo
    echo "## Extensions"
    echo "- Enable: $(jq -r '.diff.extensions_enable|join(", ")' "$plan_json")"
    echo "- Disable: $(jq -r '.diff.extensions_disable|join(", ")' "$plan_json")"
    echo
    echo "## Assets"
    echo "- Install needed:"
    jq -r '.diff.assets_install[]? | "  - \(.pack) (only=\(.only // "all"))"' "$plan_json" || echo "  - (none)"
    echo
    echo "## Runtime"
    echo "- compose_regen: $(jq -r '.runtime.compose_regen' "$plan_json")"
    echo "- compose_up: $(jq -r '.runtime.compose_up' "$plan_json")"
    echo "- remove_orphans: $(jq -r '.runtime.remove_orphans' "$plan_json")"
    echo
    echo "## Why"
    echo "- See: $cache/resource_graph.md"
    echo "- DOT: $cache/resource_graph.dot"

  } > "$plan_md"


  # v11: generate resource graph for "why"
  "$BASE_DIR/scripts/94_graph.sh" --out="$cache" >/dev/null 2>&1 || true
  log "Wrote plan:"
  echo "  $plan_json"
  echo "  $plan_md"
}

has_changes(){
  jq -e '(.diff.packs_enable|length>0) or (.diff.packs_disable|length>0) or (.diff.extensions_enable|length>0) or (.diff.extensions_disable|length>0) or (.diff.assets_install|length>0)' "$plan_json" >/dev/null 2>&1
}

apply_plan(){
  [[ -f "$plan_json" ]] || write_plan

  if ! has_changes; then
    log "No changes needed."
    return 0
  fi

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN mode. Re-run with --apply to execute."
  fi

  # Packs
  mapfile -t pe < <(jq -r '.diff.packs_enable[]?' "$plan_json")
  mapfile -t pd < <(jq -r '.diff.packs_disable[]?' "$plan_json")

  if [[ "${#pe[@]}" -gt 0 ]]; then
    run "$BASE_DIR/bin/beast" packs enable "${pe[@]}" --apply
  fi
  if [[ "${#pd[@]}" -gt 0 ]]; then
    run "$BASE_DIR/bin/beast" packs disable "${pd[@]}" --apply
  fi

  # Extensions
  mapfile -t ee < <(jq -r '.diff.extensions_enable[]?' "$plan_json")
  mapfile -t ed < <(jq -r '.diff.extensions_disable[]?' "$plan_json")

  if [[ "${#ee[@]}" -gt 0 ]]; then
    run "$BASE_DIR/bin/beast" extensions enable "${ee[@]}" --apply
  fi
  if [[ "${#ed[@]}" -gt 0 ]]; then
    run "$BASE_DIR/bin/beast" extensions disable "${ed[@]}" --apply
  fi

  # Assets
  mirror="$(jq -r '.options.mirror' "$plan_json")"
  strict_default="$(jq -r '.options.strict_url_allowlist_default' "$plan_json")"
  while read -r spec; do
    [[ -z "$spec" ]] && continue
    pack="$(jq -r '.pack' <<<"$spec")"
    only="$(jq -r '.only // "all"' <<<"$spec")"
    strict="$(jq -r '.strict // empty' <<<"$spec")"
    rag="$(jq -r '.rag // false' <<<"$spec")"

    flags=(--apply)
    if [[ "$only" != "all" && "$only" != "" ]]; then flags+=("--only=$only"); fi
    if [[ "$strict" == "true" || ( "$strict" == "" && "$strict_default" == "true" ) ]]; then flags+=(--strict); fi
    if [[ "$rag" == "true" ]]; then flags+=(--rag); fi
    if [[ -n "$mirror" && "$mirror" != "null" ]]; then flags+=("--mirror=$mirror"); fi

    run "$BASE_DIR/bin/beast" assets install "$pack" "${flags[@]}"
  done < <(jq -c '.diff.assets_install[]?' "$plan_json")

  # Apply runtime steps only if packs/exts changed OR force
  regen="$(jq -r '.runtime.compose_regen' "$plan_json")"
  up="$(jq -r '.runtime.compose_up' "$plan_json")"

  packs_or_exts_changed="$(jq -e '(.diff.packs_enable|length>0) or (.diff.packs_disable|length>0) or (.diff.extensions_enable|length>0) or (.diff.extensions_disable|length>0)' "$plan_json" >/dev/null 2>&1 && echo 1 || echo 0)"

  if [[ "$FORCE" -eq 1 || "$packs_or_exts_changed" -eq 1 ]]; then
    if [[ "$regen" == "true" ]]; then
      run "$BASE_DIR/bin/beast" compose gen --apply
    fi
    if [[ "$up" == "true" ]]; then
      run "$BASE_DIR/bin/beast" up
    fi
  else
    log "No pack/extension changes; skipping compose regen/up (use --force to force)."
  fi

  log "Reconcile complete."
}

case "$ACTION" in
  show)
    cat "$STATE_FILE"
    ;;
  actual)
    echo "packs:"
    actual_packs | sed 's/^/  - /'
    echo "extensions:"
    actual_extensions | sed 's/^/  - /'
    echo "assets_installed:"
    actual_assets_installed | sed 's/^/  - /'
    ;;
  plan)
    write_plan
    cat "$plan_md"
    ;;
  apply)
    # if plan missing or stale, rebuild
    write_plan
    apply_plan
    ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast state show [--state=path]
  ./bin/beast state actual
  ./bin/beast state plan
  ./bin/beast state apply --apply [--force] [--verbose] [--state=path]

What this is:
- Terraform-like reconciler for packs/extensions/assets.
- Computes diff: desired vs actual.
- Applies minimal changes:
  - enable/disable packs
  - enable/disable extensions
  - install missing asset packs
  - optionally regen compose + up when packs/extensions changed

Defaults:
- DRYRUN unless --apply is provided.
- Uses config/state.json unless --state=... is provided.
EOF
    ;;
esac
