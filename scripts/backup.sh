#!/usr/bin/env bash
# ==============================================================================
# AI Beast - Backup Script
# ==============================================================================
# Creates comprehensive backups of AI Beast data and configurations.
#
# Features:
#   - Full and incremental backup modes
#   - Configurable retention policy
#   - Compression with optional encryption
#   - Docker volume backup
#   - Database dump support
#   - Verification and checksums
#
# Usage:
#   ./scripts/backup.sh [OPTIONS]
#
# Options:
#   -t, --type TYPE      Backup type: full|incremental|config (default: full)
#   -o, --output DIR     Output directory (default: ./backups)
#   -c, --compress       Enable compression (default: true)
#   -e, --encrypt        Enable encryption (requires GPG)
#   -k, --keep DAYS      Keep backups for N days (default: 30)
#   -v, --verbose        Verbose output
#   -n, --dry-run        Show what would be backed up
#   -h, --help           Show this help
#
# Examples:
#   ./scripts/backup.sh                    # Full backup
#   ./scripts/backup.sh -t incremental     # Incremental backup
#   ./scripts/backup.sh -t config          # Config only
#   ./scripts/backup.sh -e -k 90           # Encrypted, 90-day retention
# ==============================================================================

set -euo pipefail

# Source common utilities if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=/dev/null
[[ -f "$SCRIPT_DIR/common.sh" ]] && source "$SCRIPT_DIR/common.sh"

# ==============================================================================
# Configuration
# ==============================================================================

# Default settings
BACKUP_TYPE="full"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
COMPRESS=true
ENCRYPT=false
RETENTION_DAYS=30
VERBOSE=false
DRY_RUN=false

# Timestamp for backup naming
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="ai_beast_backup_${TIMESTAMP}"

# Components to backup
declare -a DATA_DIRS=(
    "data"
    "models"
    "outputs"
    "workflows"
)

declare -a CONFIG_DIRS=(
    "config"
    "compose"
    "extensions"
)

declare -a CONFIG_FILES=(
    "docker-compose.yml"
    "Makefile"
    "pyproject.toml"
    "requirements.txt"
)

# Docker volumes to backup
declare -a DOCKER_VOLUMES=(
    "ai_beast_qdrant_data"
    "ai_beast_redis_data"
    "ai_beast_postgres_data"
    "ai_beast_minio_data"
)

# ==============================================================================
# Logging Functions
# ==============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_verbose() {
    [[ "$VERBOSE" == "true" ]] && echo -e "${BLUE}[DEBUG]${NC} $*"
}

# ==============================================================================
# Helper Functions
# ==============================================================================

show_help() {
    head -35 "$0" | tail -30
    exit 0
}

check_dependencies() {
    local deps=("tar" "gzip" "sha256sum")
    [[ "$ENCRYPT" == "true" ]] && deps+=("gpg")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &>/dev/null; then
            log_error "Required dependency not found: $dep"
            exit 1
        fi
    done
}

get_dir_size() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        du -sh "$dir" 2>/dev/null | cut -f1
    else
        echo "N/A"
    fi
}

create_backup_manifest() {
    local manifest_file="$1"
    
    cat > "$manifest_file" << EOF
# AI Beast Backup Manifest
# Generated: $(date -Iseconds)
# Type: $BACKUP_TYPE
# Name: $BACKUP_NAME

[metadata]
timestamp=$TIMESTAMP
type=$BACKUP_TYPE
compressed=$COMPRESS
encrypted=$ENCRYPT
hostname=$(hostname)
user=$(whoami)

[components]
EOF

    # List backed up components
    for dir in "${DATA_DIRS[@]}"; do
        [[ -d "$PROJECT_ROOT/$dir" ]] && echo "data_dir=$dir" >> "$manifest_file"
    done
    
    for dir in "${CONFIG_DIRS[@]}"; do
        [[ -d "$PROJECT_ROOT/$dir" ]] && echo "config_dir=$dir" >> "$manifest_file"
    done
    
    echo "" >> "$manifest_file"
    echo "[checksums]" >> "$manifest_file"
}

verify_backup() {
    local backup_file="$1"
    local checksum_file="${backup_file}.sha256"
    
    log_info "Verifying backup integrity..."
    
    if [[ -f "$checksum_file" ]]; then
        if sha256sum -c "$checksum_file" &>/dev/null; then
            log_success "Backup verification passed"
            return 0
        else
            log_error "Backup verification failed!"
            return 1
        fi
    else
        log_warn "No checksum file found, skipping verification"
        return 0
    fi
}

cleanup_old_backups() {
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        find "$BACKUP_DIR" -name "ai_beast_backup_*" -type f -mtime +"$RETENTION_DAYS" -print
        return
    fi
    
    local count
    count=$(find "$BACKUP_DIR" -name "ai_beast_backup_*" -type f -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
    
    if [[ "$count" -gt 0 ]]; then
        log_info "Removed $count old backup(s)"
    else
        log_verbose "No old backups to remove"
    fi
}

# ==============================================================================
# Backup Functions
# ==============================================================================

backup_directory() {
    local src_dir="$1"
    local backup_path="$2"
    local dir_name
    dir_name=$(basename "$src_dir")
    
    if [[ ! -d "$src_dir" ]]; then
        log_verbose "Skipping non-existent directory: $src_dir"
        return 0
    fi
    
    local size
    size=$(get_dir_size "$src_dir")
    log_verbose "Backing up $dir_name ($size)..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would backup: $src_dir"
        return 0
    fi
    
    # Create tar archive
    tar -cf "$backup_path/${dir_name}.tar" -C "$(dirname "$src_dir")" "$dir_name" 2>/dev/null || {
        log_warn "Warning: Some files in $dir_name may have been skipped"
    }
    
    # Compress if enabled
    if [[ "$COMPRESS" == "true" && -f "$backup_path/${dir_name}.tar" ]]; then
        gzip -f "$backup_path/${dir_name}.tar"
    fi
}

backup_files() {
    local backup_path="$1"
    shift
    local files=("$@")
    
    for file in "${files[@]}"; do
        local src="$PROJECT_ROOT/$file"
        if [[ -f "$src" ]]; then
            log_verbose "Backing up file: $file"
            if [[ "$DRY_RUN" != "true" ]]; then
                cp "$src" "$backup_path/"
            fi
        fi
    done
}

backup_docker_volumes() {
    local backup_path="$1"
    
    log_info "Backing up Docker volumes..."
    
    for volume in "${DOCKER_VOLUMES[@]}"; do
        if docker volume inspect "$volume" &>/dev/null; then
            log_verbose "Backing up volume: $volume"
            
            if [[ "$DRY_RUN" == "true" ]]; then
                log_info "[DRY-RUN] Would backup volume: $volume"
                continue
            fi
            
            # Use a temporary container to backup volume
            docker run --rm \
                -v "${volume}:/source:ro" \
                -v "${backup_path}:/backup" \
                alpine:latest \
                tar -czf "/backup/${volume}.tar.gz" -C /source . 2>/dev/null || {
                    log_warn "Failed to backup volume: $volume"
                }
        else
            log_verbose "Volume not found: $volume"
        fi
    done
}

backup_databases() {
    local backup_path="$1"
    
    log_info "Backing up databases..."
    
    # PostgreSQL backup
    if docker ps --format '{{.Names}}' | grep -q "postgres"; then
        log_verbose "Dumping PostgreSQL database..."
        
        if [[ "$DRY_RUN" != "true" ]]; then
            docker exec ai_beast_postgres \
                pg_dumpall -U postgres > "$backup_path/postgres_dump.sql" 2>/dev/null || {
                    log_warn "PostgreSQL dump failed or container not running"
                }
            
            if [[ -f "$backup_path/postgres_dump.sql" && "$COMPRESS" == "true" ]]; then
                gzip -f "$backup_path/postgres_dump.sql"
            fi
        fi
    fi
    
    # SQLite backups
    for db_file in "$PROJECT_ROOT"/data/*.db "$PROJECT_ROOT"/data/*.sqlite; do
        if [[ -f "$db_file" ]]; then
            local db_name
            db_name=$(basename "$db_file")
            log_verbose "Backing up SQLite: $db_name"
            
            if [[ "$DRY_RUN" != "true" ]]; then
                # Use SQLite backup command for consistency
                if command -v sqlite3 &>/dev/null; then
                    sqlite3 "$db_file" ".backup '$backup_path/${db_name}'" 2>/dev/null || {
                        # Fallback to copy
                        cp "$db_file" "$backup_path/"
                    }
                else
                    cp "$db_file" "$backup_path/"
                fi
            fi
        fi
    done
}

create_final_archive() {
    local backup_path="$1"
    local final_archive="$BACKUP_DIR/${BACKUP_NAME}.tar"
    
    log_info "Creating final backup archive..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create archive: $final_archive"
        return 0
    fi
    
    # Create manifest
    create_backup_manifest "$backup_path/MANIFEST"
    
    # Create final archive
    tar -cf "$final_archive" -C "$BACKUP_DIR" "$BACKUP_NAME"
    
    # Compress
    if [[ "$COMPRESS" == "true" ]]; then
        gzip -f "$final_archive"
        final_archive="${final_archive}.gz"
    fi
    
    # Encrypt if enabled
    if [[ "$ENCRYPT" == "true" ]]; then
        log_info "Encrypting backup..."
        gpg --symmetric --cipher-algo AES256 "$final_archive"
        rm -f "$final_archive"
        final_archive="${final_archive}.gpg"
    fi
    
    # Create checksum
    sha256sum "$final_archive" > "${final_archive}.sha256"
    
    # Append checksums to manifest
    echo "archive=$(sha256sum "$final_archive" | cut -d' ' -f1)" >> "$backup_path/MANIFEST"
    
    # Clean up temp directory
    rm -rf "$backup_path"
    
    echo "$final_archive"
}

# ==============================================================================
# Main Backup Functions
# ==============================================================================

backup_full() {
    log_info "Starting FULL backup..."
    
    local backup_path="$BACKUP_DIR/$BACKUP_NAME"
    mkdir -p "$backup_path"
    
    # Backup data directories
    for dir in "${DATA_DIRS[@]}"; do
        backup_directory "$PROJECT_ROOT/$dir" "$backup_path"
    done
    
    # Backup config directories
    for dir in "${CONFIG_DIRS[@]}"; do
        backup_directory "$PROJECT_ROOT/$dir" "$backup_path"
    done
    
    # Backup individual config files
    backup_files "$backup_path" "${CONFIG_FILES[@]}"
    
    # Backup Docker volumes
    backup_docker_volumes "$backup_path"
    
    # Backup databases
    backup_databases "$backup_path"
    
    # Create final archive
    local final_archive
    final_archive=$(create_final_archive "$backup_path")
    
    if [[ -n "$final_archive" ]]; then
        local size
        size=$(du -h "$final_archive" | cut -f1)
        log_success "Full backup completed: $final_archive ($size)"
    fi
}

backup_incremental() {
    log_info "Starting INCREMENTAL backup..."
    
    local backup_path="$BACKUP_DIR/$BACKUP_NAME"
    mkdir -p "$backup_path"
    
    # Find last full backup
    local last_backup
    last_backup=$(find "$BACKUP_DIR" -name "ai_beast_backup_*.tar*" -type f | sort -r | head -1)
    
    if [[ -z "$last_backup" ]]; then
        log_warn "No previous backup found, performing full backup instead"
        backup_full
        return
    fi
    
    local last_backup_time
    last_backup_time=$(stat -f %m "$last_backup" 2>/dev/null || stat -c %Y "$last_backup" 2>/dev/null)
    
    log_info "Finding files modified since last backup..."
    
    # Find and backup modified files
    for dir in "${DATA_DIRS[@]}" "${CONFIG_DIRS[@]}"; do
        if [[ -d "$PROJECT_ROOT/$dir" ]]; then
            find "$PROJECT_ROOT/$dir" -type f -newer "$last_backup" 2>/dev/null | while read -r file; do
                local rel_path="${file#$PROJECT_ROOT/}"
                local dest_dir="$backup_path/$(dirname "$rel_path")"
                
                if [[ "$DRY_RUN" == "true" ]]; then
                    log_info "[DRY-RUN] Would backup: $rel_path"
                else
                    mkdir -p "$dest_dir"
                    cp "$file" "$dest_dir/"
                fi
            done
        fi
    done
    
    # Create final archive
    local final_archive
    final_archive=$(create_final_archive "$backup_path")
    
    if [[ -n "$final_archive" ]]; then
        local size
        size=$(du -h "$final_archive" | cut -f1)
        log_success "Incremental backup completed: $final_archive ($size)"
    fi
}

backup_config() {
    log_info "Starting CONFIG-ONLY backup..."
    
    local backup_path="$BACKUP_DIR/$BACKUP_NAME"
    mkdir -p "$backup_path"
    
    # Backup config directories only
    for dir in "${CONFIG_DIRS[@]}"; do
        backup_directory "$PROJECT_ROOT/$dir" "$backup_path"
    done
    
    # Backup config files
    backup_files "$backup_path" "${CONFIG_FILES[@]}"
    
    # Create final archive
    local final_archive
    final_archive=$(create_final_archive "$backup_path")
    
    if [[ -n "$final_archive" ]]; then
        local size
        size=$(du -h "$final_archive" | cut -f1)
        log_success "Config backup completed: $final_archive ($size)"
    fi
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -t|--type)
                BACKUP_TYPE="$2"
                shift 2
                ;;
            -o|--output)
                BACKUP_DIR="$2"
                shift 2
                ;;
            -c|--compress)
                COMPRESS=true
                shift
                ;;
            --no-compress)
                COMPRESS=false
                shift
                ;;
            -e|--encrypt)
                ENCRYPT=true
                shift
                ;;
            -k|--keep)
                RETENTION_DAYS="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    log_info "AI Beast Backup - $(date)"
    log_info "Backup type: $BACKUP_TYPE"
    log_info "Output directory: $BACKUP_DIR"
    
    # Check dependencies
    check_dependencies
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Run backup based on type
    case "$BACKUP_TYPE" in
        full)
            backup_full
            ;;
        incremental)
            backup_incremental
            ;;
        config)
            backup_config
            ;;
        *)
            log_error "Unknown backup type: $BACKUP_TYPE"
            exit 1
            ;;
    esac
    
    # Cleanup old backups
    cleanup_old_backups
    
    log_success "Backup process completed!"
}

# Run main function
main "$@"
