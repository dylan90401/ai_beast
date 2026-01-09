#!/usr/bin/env bash
# extensions.sh — Extension management helpers
# AI Beast / Kryptos
#
# Extensions are pluggable service bundles in extensions/<name>/
# Each extension can provide:
#   - compose.fragment.yaml  (Docker services)
#   - install.sh             (Setup script)
#   - enabled                (Marker file when active)
#   - README.md              (Documentation)

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
[[ -f "$SCRIPT_LIB_DIR/common.sh" ]] && source "$SCRIPT_LIB_DIR/common.sh"

# ─────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────

# Get extensions directory
ext_dir() {
  echo "${BASE_DIR:-$(pwd)}/extensions"
}

# List all available extensions
ext_list_all() {
  local dir
  dir="$(ext_dir)"
  [[ -d "$dir" ]] || return 0
  
  for d in "$dir"/*/; do
    [[ -d "$d" ]] || continue
    local name
    name="$(basename "$d")"
    # Skip hidden and example dirs
    [[ "$name" == "."* ]] && continue
    echo "$name"
  done | sort
}

# List enabled extensions
ext_list_enabled() {
  local dir
  dir="$(ext_dir)"
  [[ -d "$dir" ]] || return 0
  
  for d in "$dir"/*/; do
    [[ -d "$d" ]] || continue
    [[ -f "$d/enabled" ]] || continue
    basename "$d"
  done | sort
}

# List disabled extensions
ext_list_disabled() {
  local dir
  dir="$(ext_dir)"
  [[ -d "$dir" ]] || return 0
  
  for d in "$dir"/*/; do
    [[ -d "$d" ]] || continue
    [[ -f "$d/enabled" ]] && continue
    local name
    name="$(basename "$d")"
    [[ "$name" == "."* ]] && continue
    echo "$name"
  done | sort
}

# ─────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────

# Check if extension exists
ext_exists() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  [[ -d "$dir" ]]
}

# Check if extension is enabled
ext_is_enabled() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  [[ -f "$dir/enabled" ]]
}

# Check if extension has compose fragment
ext_has_compose() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  [[ -f "$dir/compose.fragment.yaml" ]]
}

# Check if extension has install script
ext_has_install() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  [[ -f "$dir/install.sh" ]]
}

# Get extension info
ext_info() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  
  if ! ext_exists "$name"; then
    echo "Extension not found: $name"
    return 1
  fi
  
  echo "Extension: $name"
  echo "  Path: $dir"
  echo "  Status: $(ext_is_enabled "$name" && echo "enabled" || echo "disabled")"
  echo "  Has compose: $(ext_has_compose "$name" && echo "yes" || echo "no")"
  echo "  Has install: $(ext_has_install "$name" && echo "yes" || echo "no")"
  
  # Show README excerpt if available
  if [[ -f "$dir/README.md" ]]; then
    echo "  Description:"
    head -5 "$dir/README.md" | sed 's/^/    /'
  fi
}

# ─────────────────────────────────────────────────────────────
# Enable/Disable
# ─────────────────────────────────────────────────────────────

# Enable an extension
ext_enable() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  
  if ! ext_exists "$name"; then
    log_error "Extension not found: $name"
    return 1
  fi
  
  if ext_is_enabled "$name"; then
    log_info "Extension already enabled: $name"
    return 0
  fi
  
  log_info "Enabling extension: $name"
  
  # Run install script if present
  if ext_has_install "$name"; then
    if [[ "${DRYRUN:-1}" -eq 1 ]]; then
      log_dryrun "Would run: $dir/install.sh --apply"
    else
      bash "$dir/install.sh" --apply
    fi
  fi
  
  # Create enabled marker
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would create: $dir/enabled"
  else
    touch "$dir/enabled"
  fi
  
  log_success "Extension enabled: $name"
}

# Disable an extension
ext_disable() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  
  if ! ext_exists "$name"; then
    log_error "Extension not found: $name"
    return 1
  fi
  
  if ! ext_is_enabled "$name"; then
    log_info "Extension already disabled: $name"
    return 0
  fi
  
  log_info "Disabling extension: $name"
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would remove: $dir/enabled"
  else
    rm -f "$dir/enabled"
  fi
  
  log_success "Extension disabled: $name"
}

# ─────────────────────────────────────────────────────────────
# Compose Integration
# ─────────────────────────────────────────────────────────────

# Get list of enabled compose fragments
ext_compose_fragments() {
  local dir
  dir="$(ext_dir)"
  
  for name in $(ext_list_enabled); do
    local frag="$dir/$name/compose.fragment.yaml"
    [[ -f "$frag" ]] && echo "$frag"
  done
}

# Merge all enabled extension fragments into a single file
ext_merge_compose() {
  local output="${1:-/dev/stdout}"
  local fragments
  fragments=$(ext_compose_fragments)
  
  if [[ -z "$fragments" ]]; then
    log_info "No extension compose fragments to merge"
    return 0
  fi
  
  log_info "Merging extension compose fragments..."
  
  # Start with header
  {
    echo "# AUTO-GENERATED by AI Beast"
    echo "# Extensions compose overlay"
    echo "# Do not edit manually"
    echo ""
    echo "services:"
  } > "$output"
  
  # Merge each fragment
  for frag in $fragments; do
    local name
    name="$(basename "$(dirname "$frag")")"
    {
      echo ""
      echo "  # --- Extension: $name ---"
      # Extract services section (skip header lines)
      awk '/^services:/{found=1; next} found && /^[^ ]/{exit} found{print}' "$frag"
    } >> "$output"
  done
  
  log_success "Merged $(echo "$fragments" | wc -w | tr -d ' ') extension fragments"
}

# ─────────────────────────────────────────────────────────────
# Profile-Based Enable
# ─────────────────────────────────────────────────────────────

# Define extensions for each profile
ext_profile_extensions() {
  local profile="$1"
  
  case "$profile" in
    lite)
      echo "minio"
      ;;
    full)
      echo "minio searxng otel_collector flowise langflow"
      ;;
    prodish)
      echo "minio searxng otel_collector flowise langflow dify apache_tika unstructured_api"
      ;;
    *)
      log_warn "Unknown profile: $profile"
      return 1
      ;;
  esac
}

# Enable extensions for a profile
ext_enable_profile() {
  local profile="$1"
  local extensions
  extensions=$(ext_profile_extensions "$profile")
  
  if [[ -z "$extensions" ]]; then
    return 1
  fi
  
  log_info "Enabling extensions for profile: $profile"
  
  for ext in $extensions; do
    if ext_exists "$ext"; then
      ext_enable "$ext"
    else
      log_warn "Extension not found (skipping): $ext"
    fi
  done
}

# ─────────────────────────────────────────────────────────────
# Scaffolding
# ─────────────────────────────────────────────────────────────

# Create a new extension scaffold
ext_create() {
  local name="$1"
  local dir
  dir="$(ext_dir)/$name"
  
  if ext_exists "$name"; then
    log_error "Extension already exists: $name"
    return 1
  fi
  
  log_info "Creating extension scaffold: $name"
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would create: $dir/{install.sh,compose.fragment.yaml,README.md}"
    return 0
  fi
  
  mkdir -p "$dir"
  
  # Create install.sh
  cat > "$dir/install.sh" << 'INSTALL_EOF'
#!/usr/bin/env bash
set -euo pipefail

APPLY=0
for arg in "${@:-}"; do [[ "$arg" == "--apply" ]] && APPLY=1; done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/../.." && pwd)"

log(){ echo "[ext:EXTENSION_NAME] $*"; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRYRUN: would enable EXTENSION_NAME extension"
  exit 0
fi

# Add your setup logic here

touch "$script_dir/enabled"
log "Enabled EXTENSION_NAME extension"
INSTALL_EOF
  sed -i '' "s/EXTENSION_NAME/$name/g" "$dir/install.sh"
  chmod +x "$dir/install.sh"
  
  # Create compose fragment
  cat > "$dir/compose.fragment.yaml" << COMPOSE_EOF
# $name extension compose fragment
services:
  $name:
    image: alpine:latest
    profiles: ["$name"]
    # TODO: Configure your service
    command: ["sleep", "infinity"]
COMPOSE_EOF
  
  # Create README
  cat > "$dir/README.md" << README_EOF
# $name Extension

TODO: Add description

## Enable

\`\`\`bash
./bin/beast extensions enable $name --apply
./bin/beast compose gen --apply
./bin/beast up
\`\`\`

## Configuration

TODO: Document configuration options
README_EOF
  
  log_success "Created extension scaffold: $dir"
  log_info "Next steps:"
  log_info "  1. Edit $dir/compose.fragment.yaml"
  log_info "  2. Edit $dir/install.sh"
  log_info "  3. ./bin/beast extensions enable $name --apply"
}
