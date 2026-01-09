#!/usr/bin/env bash
# backup.sh — Backup and restore helpers
# AI Beast / Kryptos
#
# Provides backup/restore functionality with profile support.

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
[[ -f "$SCRIPT_LIB_DIR/common.sh" ]] && source "$SCRIPT_LIB_DIR/common.sh"

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

# Default backup settings
BACKUP_CHUNK_SIZE="${BACKUP_CHUNK_SIZE:-2g}"
BACKUP_COMPRESSION="${BACKUP_COMPRESSION:-gzip}"

# ─────────────────────────────────────────────────────────────
# Profile Definitions
# ─────────────────────────────────────────────────────────────

# Define what each backup profile includes
# min: config only
# standard: config + data + outputs
# full: everything including models
# appliance: everything for full system restore

backup_profile_paths() {
  local profile="$1"
  local base="${BASE_DIR:-$(pwd)}"
  
  case "$profile" in
    min|minimal)
      echo "$base/config"
      echo "$base/beast/registry.json"
      ;;
    standard)
      echo "$base/config"
      echo "$base/beast"
      echo "${DATA_DIR:-$base/data}"
      echo "${OUTPUTS_DIR:-$base/outputs}"
      ;;
    full)
      echo "$base/config"
      echo "$base/beast"
      echo "${DATA_DIR:-$base/data}"
      echo "${OUTPUTS_DIR:-$base/outputs}"
      echo "${MODELS_DIR:-$base/models}"
      echo "${CACHE_DIR:-$base/cache}"
      ;;
    appliance)
      echo "$base"
      ;;
    *)
      log_warn "Unknown backup profile: $profile (using standard)"
      backup_profile_paths "standard"
      ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# Backup Functions
# ─────────────────────────────────────────────────────────────

# Create backup directory name with timestamp
backup_dirname() {
  local prefix="${1:-backup}"
  echo "${prefix}_$(date +%Y%m%d_%H%M%S)"
}

# Get backup destination
backup_dest_dir() {
  local name="$1"
  local backup_root="${BACKUP_DIR:-${BASE_DIR:-$(pwd)}/backups}"
  echo "$backup_root/snapshots/$name"
}

# Calculate total size of paths
backup_calc_size() {
  local total=0
  for path in "$@"; do
    if [[ -e "$path" ]]; then
      local size
      size=$(du -sk "$path" 2>/dev/null | awk '{print $1}' || echo 0)
      total=$((total + size))
    fi
  done
  echo $total
}

# Create manifest file
backup_create_manifest() {
  local dest="$1"
  shift
  local paths=("$@")
  
  local manifest="$dest/manifest.sha256"
  
  log_info "Creating backup manifest..."
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would create manifest at $manifest"
    return 0
  fi
  
  : > "$manifest"
  for path in "${paths[@]}"; do
    if [[ -d "$path" ]]; then
      find "$path" -type f -exec shasum -a 256 {} \; >> "$manifest" 2>/dev/null || true
    elif [[ -f "$path" ]]; then
      shasum -a 256 "$path" >> "$manifest" 2>/dev/null || true
    fi
  done
  
  log_info "Manifest: $(wc -l < "$manifest" | tr -d ' ') files"
}

# Create backup tarball
backup_create_tarball() {
  local dest="$1"
  local name="$2"
  shift 2
  local paths=("$@")
  
  local tarball="$dest/${name}.tgz"
  
  log_info "Creating tarball: $tarball"
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would create $tarball"
    return 0
  fi
  
  # Build tar command
  local tar_args=("-czf" "$tarball")
  
  for path in "${paths[@]}"; do
    [[ -e "$path" ]] && tar_args+=("$path")
  done
  
  tar "${tar_args[@]}"
  
  # Optionally split if too large
  if [[ "$BACKUP_CHUNK_SIZE" != "0" ]]; then
    local size_kb
    size_kb=$(du -k "$tarball" | awk '{print $1}')
    local chunk_kb
    chunk_kb=$(echo "$BACKUP_CHUNK_SIZE" | sed 's/g/*1024*1024/;s/m/*1024/' | bc)
    
    if [[ $size_kb -gt $chunk_kb ]]; then
      log_info "Splitting large backup into chunks..."
      split -b "$BACKUP_CHUNK_SIZE" "$tarball" "${tarball}.part."
      rm "$tarball"
    fi
  fi
  
  log_success "Backup created: $dest"
}

# Main backup function
backup_create() {
  local profile="${1:-standard}"
  local name="${2:-$(backup_dirname "backup")}"
  
  log_info "Creating backup (profile: $profile, name: $name)"
  
  # Get paths for profile
  local paths=()
  while IFS= read -r path; do
    [[ -n "$path" ]] && paths+=("$path")
  done < <(backup_profile_paths "$profile")
  
  if [[ ${#paths[@]} -eq 0 ]]; then
    log_error "No paths to backup"
    return 1
  fi
  
  # Calculate size
  local size_kb
  size_kb=$(backup_calc_size "${paths[@]}")
  log_info "Estimated backup size: $((size_kb / 1024)) MB"
  
  # Create destination
  local dest
  dest=$(backup_dest_dir "$name")
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    log_dryrun "Would backup to: $dest"
    log_dryrun "Paths: ${paths[*]}"
    return 0
  fi
  
  mkdir -p "$dest"
  
  # Create manifest
  backup_create_manifest "$dest" "${paths[@]}"
  
  # Create tarball
  backup_create_tarball "$dest" "backup" "${paths[@]}"
  
  # Save metadata
  cat > "$dest/metadata.json" << EOF
{
  "created": "$(date -Iseconds)",
  "profile": "$profile",
  "size_kb": $size_kb,
  "paths": $(printf '%s\n' "${paths[@]}" | jq -R . | jq -s .)
}
EOF
  
  log_success "Backup complete: $dest"
}

# ─────────────────────────────────────────────────────────────
# Restore Functions
# ─────────────────────────────────────────────────────────────

# List available backups
backup_list() {
  local backup_root="${BACKUP_DIR:-${BASE_DIR:-$(pwd)}/backups}"
  local snapshots="$backup_root/snapshots"
  
  if [[ ! -d "$snapshots" ]]; then
    log_info "No backups found"
    return 0
  fi
  
  echo "Available Backups"
  echo "================="
  
  for dir in "$snapshots"/*/; do
    [[ -d "$dir" ]] || continue
    local name
    name=$(basename "$dir")
    local meta="$dir/metadata.json"
    
    if [[ -f "$meta" ]] && command_exists jq; then
      local profile
      profile=$(jq -r '.profile // "unknown"' "$meta")
      local created
      created=$(jq -r '.created // "unknown"' "$meta")
      local size_kb
      size_kb=$(jq -r '.size_kb // 0' "$meta")
      printf "  %-30s [%-8s] %s (%d MB)\n" "$name" "$profile" "$created" "$((size_kb / 1024))"
    else
      echo "  $name"
    fi
  done
}

# Verify backup integrity
backup_verify() {
  local src="$1"
  
  if [[ ! -d "$src" ]]; then
    log_error "Backup not found: $src"
    return 1
  fi
  
  local manifest="$src/manifest.sha256"
  if [[ ! -f "$manifest" ]]; then
    log_warn "No manifest found in backup"
    return 1
  fi
  
  log_info "Verifying backup integrity..."
  
  local errors=0
  while IFS= read -r line; do
    local hash file
    hash=$(echo "$line" | awk '{print $1}')
    file=$(echo "$line" | awk '{print $2}')
    
    if [[ -f "$file" ]]; then
      local actual
      actual=$(shasum -a 256 "$file" | awk '{print $1}')
      if [[ "$actual" != "$hash" ]]; then
        log_warn "Hash mismatch: $file"
        ((errors++))
      fi
    fi
  done < "$manifest"
  
  if [[ $errors -eq 0 ]]; then
    log_success "Backup verified successfully"
    return 0
  else
    log_error "$errors files failed verification"
    return 1
  fi
}

# Restore from backup
backup_restore() {
  local src="$1"
  local target="${2:-${BASE_DIR:-$(pwd)}}"
  
  if [[ ! -d "$src" ]]; then
    log_error "Backup not found: $src"
    return 1
  fi
  
  log_info "Restoring backup from: $src"
  log_info "Target: $target"
  
  # Find tarball (may be split)
  local tarball="$src/backup.tgz"
  local parts=("$src"/backup.tgz.part.*)
  
  if [[ "${DRYRUN:-1}" -eq 1 ]]; then
    if [[ -f "$tarball" ]]; then
      log_dryrun "Would restore from: $tarball"
    elif [[ ${#parts[@]} -gt 0 && -f "${parts[0]}" ]]; then
      log_dryrun "Would restore from ${#parts[@]} parts"
    else
      log_error "No backup tarball found"
      return 1
    fi
    return 0
  fi
  
  # Reassemble if split
  if [[ ! -f "$tarball" && ${#parts[@]} -gt 0 && -f "${parts[0]}" ]]; then
    log_info "Reassembling split backup..."
    cat "$src"/backup.tgz.part.* > "$tarball"
  fi
  
  if [[ ! -f "$tarball" ]]; then
    log_error "No backup tarball found"
    return 1
  fi
  
  # Extract
  log_info "Extracting backup..."
  tar -xzf "$tarball" -C "$target"
  
  log_success "Restore complete"
}
