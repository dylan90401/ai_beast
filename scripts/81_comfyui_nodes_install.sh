#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-help}"; shift || true
APPLY=0
STRICT=0
PACK=""

for arg in "${@:-}"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --strict) STRICT=1 ;;
    --pack=*) PACK="${arg#--pack=}" ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"
die(){ echo "[nodes] ERROR: $*" >&2; exit 1; }
log(){ echo "[nodes] $*"; }

[[ -f "$BASE_DIR/config/paths.env" ]] || die "Missing config/paths.env (run: ./bin/beast init --apply)"
# shellcheck disable=SC1090
source "$BASE_DIR/config/paths.env"

cfg="$BASE_DIR/config/packs.json"
allow="$BASE_DIR/config/comfy_nodes_allowlist.txt"

need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing '$1'"; }
need_cmd jq
need_cmd git

[[ -d "${COMFYUI_DIR:-}" ]] || die "COMFYUI_DIR not found: ${COMFYUI_DIR:-}"
mkdir -p "$COMFYUI_DIR/custom_nodes"

is_allowed_repo(){
  local repo="$1"
  [[ -f "$allow" ]] || return 0
  grep -Fqx "$repo" "$allow"
}

pip_reqs_if_any(){
  local node_dir="$1"
  local req="$node_dir/requirements.txt"
  [[ -f "$req" ]] || return 0
  [[ -n "${VENV_DIR:-}" ]] || { log "No VENV_DIR set; skipping pip requirements for $node_dir"; return 0; }

  if [[ "$APPLY" -ne 1 ]]; then
    log "DRYRUN: would pip3 install -r $req (venv=$VENV_DIR)"
    return 0
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  pip3 install -U pip wheel setuptools >/dev/null
  pip3 install -r "$req" || log "WARN: pip3 install failed for $req"
  deactivate || true
}

install_one(){
  local name="$1" repo="$2" pipreq="$3"
  if [[ "$STRICT" -eq 1 ]] && ! is_allowed_repo "$repo"; then
    die "Repo not in allowlist (strict mode): $repo"
  fi

  if [[ -f "$allow" ]] && ! is_allowed_repo "$repo"; then
    log "WARN: repo not allowlisted: $repo"
  fi

  local dest="$COMFYUI_DIR/custom_nodes/$name"
  if [[ -d "$dest/.git" ]]; then
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would update $name"
    else
      (cd "$dest" && git pull --rebase) || log "WARN: update failed for $name"
    fi
  else
    if [[ "$APPLY" -ne 1 ]]; then
      log "DRYRUN: would clone $repo -> $dest"
    else
      git clone "$repo" "$dest" || die "Clone failed: $repo"
    fi
  fi

  if [[ "$pipreq" == "true" ]]; then
    pip_reqs_if_any "$dest"
  fi
  log "Installed: $name"
}

install_pack_nodes(){
  local pack="$1"
  local exists
  exists="$(jq -r --arg n "$pack" '.packs[$n] != null' "$cfg")"
  [[ "$exists" == "true" ]] || die "Unknown pack: $pack"

  mapfile -t names < <(jq -r --arg n "$pack" '.packs[$n].comfyui_nodes[]? | .name' "$cfg")
  mapfile -t repos  < <(jq -r --arg n "$pack" '.packs[$n].comfyui_nodes[]? | .repo' "$cfg")
  mapfile -t pipr   < <(jq -r --arg n "$pack" '.packs[$n].comfyui_nodes[]? | .pip_requirements' "$cfg")

  [[ "${#names[@]}" -gt 0 ]] || { log "No ComfyUI nodes defined for pack: $pack"; return 0; }

  log "Installing ComfyUI node bundle for pack: $pack"
  for i in "${!names[@]}"; do
    install_one "${names[$i]}" "${repos[$i]}" "${pipr[$i]}"
  done
}

case "$ACTION" in
  install)
    if [[ -n "$PACK" ]]; then
      install_pack_nodes "$PACK"
      exit 0
    fi
    if [[ -z "${1:-}" || -z "${2:-}" ]]; then
      die "Usage: nodes install --pack=<pack> [--apply] [--strict] OR nodes install <name> <repo> [--apply] [--strict]"
    fi
    install_one "$1" "$2" "true"
    ;;
  allowlist)
    log "Allowlist: $allow"
    [[ -f "$allow" ]] && cat "$allow" || true
    ;;
  *)
    cat <<EOF
Usage:
  ./bin/beast nodes install --pack=<pack> [--apply] [--strict]
  ./bin/beast nodes install <name> <repo> [--apply] [--strict]
  ./bin/beast nodes allowlist

Notes:
- --strict blocks non-allowlisted repos.
- requirements.txt (if present) is installed into VENV_DIR.
EOF
    ;;
esac
