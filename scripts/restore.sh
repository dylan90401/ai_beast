#!/usr/bin/env bash
# ==============================================================================
# AI Beast - Restore Script
# ==============================================================================
# Restores AI Beast data and configurations from backups.
#
# Features:
#   - Full and partial restore modes
#   - Pre-restore validation
#   - Automatic backup before restore
#   - Docker volume restoration
#   - Database restore support
#   - Dry-run mode for verification
#
# Usage:
#   ./scripts/restore.sh [OPTIONS] <backup_file>
#
# Options:
#   -c, --components LIST  Components to restore (comma-separated)
#                          Values: all|data|config|volumes|databases
#   -b, --backup           Create backup before restore (default: true)
#   -f, --force            Force restore without confirmation
#   -v, --verbose          Verbose output
#   -n, --dry-run          Show what would be restored
#   -h, --help             Show this help
#
# Examples:
#   ./scripts/restore.sh backup.tar.gz                    # Full restore
#   ./scripts/restore.sh -c config backup.tar.gz          # Config only
#   ./scripts/restore.sh -c data,databases backup.tar.gz  # Data + DBs
#   ./scripts/restore.sh -n backup.tar.gz                 # Dry run
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
COMPONENTS="all"
PRE_BACKUP=true
FORCE=false
VERBOSE=false
DRY_RUN=false
BACKUP_FILE=""

# Temp directory for extraction
TEMP_DIR=""

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
    head -32 "$0" | tail -27
    exit 0
}

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        log_verbose "Cleaning up temp directory..."
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

check_dependencies() {
    local deps=("tar" "gzip" "sha256sum")
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &>/dev/null; then
            log_error "Required dependency not found: $dep"
            exit 1
        fi
    done
}

verify_backup_file() {
    local backup_file="$1"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    # Check for checksum file
    local checksum_file="${backup_file}.sha256"
    if [[ -f "$checksum_file" ]]; then
        log_info "Verifying backup integrity..."
        if sha256sum -c "$checksum_file" &>/dev/null; then
            log_success "Backup integrity verified"
        else
            log_error "Backup integrity check failed!"
            if [[ "$FORCE" != "true" ]]; then
                exit 1
            fi
            log_warn "Continuing due to --force flag"
        fi
    else
        log_warn "No checksum file found, skipping integrity check"
    fi
}

confirm_restore() {
    if [[ "$FORCE" == "true" || "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    echo ""
    log_warn "This will restore data from: $BACKUP_FILE"
    log_warn "Components to restore: $COMPONENTS"
    log_warn "Existing data may be overwritten!"
    echo ""
    
    read -r -p "Are you sure you want to continue? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            log_info "Restore cancelled"
            exit 0
            ;;
    esac
}

extract_backup() {
    local backup_file="$1"
    
    TEMP_DIR=$(mktemp -d)
    log_verbose "Extracting to: $TEMP_DIR"
    
    local actual_file="$backup_file"
    
    # Handle encrypted files
    if [[ "$backup_file" == *.gpg ]]; then
        log_info "Decrypting backup..."
        gpg --decrypt "$backup_file" > "${TEMP_DIR}/backup.tar.gz"
        actual_file="${TEMP_DIR}/backup.tar.gz"
    fi
    
    # Extract based on compression
    if [[ "$actual_file" == *.tar.gz || "$actual_file" == *.tgz ]]; then
        tar -xzf "$actual_file" -C "$TEMP_DIR"
    elif [[ "$actual_file" == *.tar ]]; then
        tar -xf "$actual_file" -C "$TEMP_DIR"
    else
        log_error "Unknown archive format: $actual_file"
        exit 1
    fi
    
    # Find the backup directory (should be ai_beast_backup_*)
    local backup_dir
    backup_dir=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "ai_beast_backup_*" | head -1)
    
    if [[ -z "$backup_dir" ]]; then
        # Maybe files are directly in temp dir
        backup_dir="$TEMP_DIR"
    fi
    
    echo "$backup_dir"
}

should_restore_component() {
    local component="$1"
    
    if [[ "$COMPONENTS" == "all" ]]; then
        return 0
    fi
    
    if [[ ",$COMPONENTS," == *",$component,"* ]]; then
        return 0
    fi
    
    return 1
}

# ==============================================================================
# Restore Functions
# ==============================================================================

restore_directory() {
    local archive="$1"
    local dest_dir="$2"
    
    if [[ ! -f "$archive" ]]; then
        log_verbose "Archive not found: $archive"
        return 0
    fi
    
    local dir_name
    dir_name=$(basename "$archive" .tar.gz)
    dir_name=$(basename "$dir_name" .tar)
    
    log_info "Restoring: $dir_name"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would restore: $archive -> $dest_dir"
        return 0
    fi
    
    # Create destination if needed
    mkdir -p "$dest_dir"
    
    # Backup existing directory
    if [[ -d "$dest_dir/$dir_name" ]]; then
        log_verbose "Existing directory found, will be replaced"
    fi
    
    # Extract archive
    if [[ "$archive" == *.tar.gz ]]; then
        tar -xzf "$archive" -C "$dest_dir"
    else
        tar -xf "$archive" -C "$dest_dir"
    fi
    
    log_success "Restored: $dir_name"
}

restore_data() {
    local backup_dir="$1"
    
    if ! should_restore_component "data"; then
        log_verbose "Skipping data restoration"
        return 0
    fi
    
    log_info "Restoring data directories..."
    
    for archive in "$backup_dir"/*.tar.gz "$backup_dir"/*.tar; do
        if [[ -f "$archive" ]]; then
            local name
            name=$(basename "$archive" .tar.gz)
            name=$(basename "$name" .tar)
            
            # Check if it's a data directory
            case "$name" in
                data|models|outputs|workflows)
                    restore_directory "$archive" "$PROJECT_ROOT"
                    ;;
            esac
        fi
    done
}

restore_config() {
    local backup_dir="$1"
    
    if ! should_restore_component "config"; then
        log_verbose "Skipping config restoration"
        return 0
    fi
    
    log_info "Restoring configuration..."
    
    # Restore config directories
    for archive in "$backup_dir"/*.tar.gz "$backup_dir"/*.tar; do
        if [[ -f "$archive" ]]; then
            local name
            name=$(basename "$archive" .tar.gz)
            name=$(basename "$name" .tar)
            
            # Check if it's a config directory
            case "$name" in
                config|compose|extensions)
                    restore_directory "$archive" "$PROJECT_ROOT"
                    ;;
            esac
        fi
    done
    
    # Restore individual config files
    for file in docker-compose.yml Makefile pyproject.toml requirements.txt; do
        if [[ -f "$backup_dir/$file" ]]; then
            log_verbose "Restoring file: $file"
            if [[ "$DRY_RUN" != "true" ]]; then
                cp "$backup_dir/$file" "$PROJECT_ROOT/"
            fi
        fi
    done
}

restore_docker_volumes() {
    local backup_dir="$1"
    
    if ! should_restore_component "volumes"; then
        log_verbose "Skipping Docker volume restoration"
        return 0
    fi
    
    log_info "Restoring Docker volumes..."
    
    for archive in "$backup_dir"/*.tar.gz; do
        if [[ -f "$archive" ]]; then
            local name
            name=$(basename "$archive" .tar.gz)
            
            # Check if it's a volume backup
            if [[ "$name" == ai_beast_*_data ]]; then
                log_info "Restoring volume: $name"
                
                if [[ "$DRY_RUN" == "true" ]]; then
                    log_info "[DRY-RUN] Would restore volume: $name"
                    continue
                fi
                
                # Create volume if it doesn't exist
                if ! docker volume inspect "$name" &>/dev/null; then
                    docker volume create "$name"
                fi
                
                # Restore using temporary container
                docker run --rm \
                    -v "${name}:/dest" \
                    -v "${archive}:/backup.tar.gz:ro" \
                    alpine:latest \
                    sh -c "rm -rf /dest/* && tar -xzf /backup.tar.gz -C /dest" || {
                        log_warn "Failed to restore volume: $name"
                    }
                
                log_success "Restored volume: $name"
            fi
        fi
    done
}

restore_databases() {
    local backup_dir="$1"
    
    if ! should_restore_component "databases"; then
        log_verbose "Skipping database restoration"
        return 0
    fi
    
    log_info "Restoring databases..."
    
    # Restore PostgreSQL
    local pg_dump="$backup_dir/postgres_dump.sql"
    local pg_dump_gz="$backup_dir/postgres_dump.sql.gz"
    
    if [[ -f "$pg_dump_gz" ]]; then
        log_info "Restoring PostgreSQL database..."
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY-RUN] Would restore PostgreSQL database"
        else
            # Check if PostgreSQL container is running
            if docker ps --format '{{.Names}}' | grep -q "postgres"; then
                gunzip -c "$pg_dump_gz" | docker exec -i ai_beast_postgres \
                    psql -U postgres || {
                        log_warn "PostgreSQL restore failed"
                    }
                log_success "PostgreSQL database restored"
            else
                log_warn "PostgreSQL container not running, skipping restore"
            fi
        fi
    elif [[ -f "$pg_dump" ]]; then
        if [[ "$DRY_RUN" != "true" ]]; then
            if docker ps --format '{{.Names}}' | grep -q "postgres"; then
                docker exec -i ai_beast_postgres psql -U postgres < "$pg_dump" || {
                    log_warn "PostgreSQL restore failed"
                }
            fi
        fi
    fi
    
    # Restore SQLite databases
    for db_file in "$backup_dir"/*.db "$backup_dir"/*.sqlite; do
        if [[ -f "$db_file" ]]; then
            local db_name
            db_name=$(basename "$db_file")
            
            log_info "Restoring SQLite: $db_name"
            
            if [[ "$DRY_RUN" == "true" ]]; then
                log_info "[DRY-RUN] Would restore: $db_name"
            else
                mkdir -p "$PROJECT_ROOT/data"
                cp "$db_file" "$PROJECT_ROOT/data/"
                log_success "Restored: $db_name"
            fi
        fi
    done
}

create_pre_restore_backup() {
    if [[ "$PRE_BACKUP" != "true" || "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    log_info "Creating pre-restore backup..."
    
    if [[ -x "$SCRIPT_DIR/backup.sh" ]]; then
        "$SCRIPT_DIR/backup.sh" -t full -o "$PROJECT_ROOT/backups/pre_restore" || {
            log_warn "Pre-restore backup failed, continuing anyway"
        }
    else
        log_warn "Backup script not found, skipping pre-restore backup"
    fi
}

# ==============================================================================
# Main Restore Function
# ==============================================================================

do_restore() {
    # Verify backup file
    verify_backup_file "$BACKUP_FILE"
    
    # Confirm with user
    confirm_restore
    
    # Create pre-restore backup
    create_pre_restore_backup
    
    # Extract backup
    log_info "Extracting backup..."
    local backup_dir
    backup_dir=$(extract_backup "$BACKUP_FILE")
    log_verbose "Backup extracted to: $backup_dir"
    
    # Check manifest
    if [[ -f "$backup_dir/MANIFEST" ]]; then
        log_verbose "Backup manifest found"
        if [[ "$VERBOSE" == "true" ]]; then
            cat "$backup_dir/MANIFEST"
        fi
    fi
    
    # Stop services before restore
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Stopping services..."
        cd "$PROJECT_ROOT"
        make stop 2>/dev/null || docker compose down 2>/dev/null || true
    fi
    
    # Restore components
    restore_data "$backup_dir"
    restore_config "$backup_dir"
    restore_docker_volumes "$backup_dir"
    restore_databases "$backup_dir"
    
    # Restart services
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "Restarting services..."
        cd "$PROJECT_ROOT"
        make start 2>/dev/null || docker compose up -d 2>/dev/null || true
    fi
    
    log_success "Restore completed!"
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -c|--components)
                COMPONENTS="$2"
                shift 2
                ;;
            -b|--backup)
                PRE_BACKUP=true
                shift
                ;;
            --no-backup)
                PRE_BACKUP=false
                shift
                ;;
            -f|--force)
                FORCE=true
                shift
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
            -*)
                log_error "Unknown option: $1"
                exit 1
                ;;
            *)
                BACKUP_FILE="$1"
                shift
                ;;
        esac
    done
    
    # Validate backup file argument
    if [[ -z "$BACKUP_FILE" ]]; then
        log_error "No backup file specified"
        echo "Usage: $0 [OPTIONS] <backup_file>"
        exit 1
    fi
    
    log_info "AI Beast Restore - $(date)"
    log_info "Backup file: $BACKUP_FILE"
    log_info "Components: $COMPONENTS"
    
    # Check dependencies
    check_dependencies
    
    # Run restore
    do_restore
}

# Run main function
main "$@"
