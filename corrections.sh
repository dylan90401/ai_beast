#!/bin/bash

# AI Beast Refactor and Enhancement Script
# This script refactors and enhances the AI Beast toolkit functionality

set -euo pipefail  # Exit on any error, unset vars are errors, and pipelines fail on first error
IFS=$'\n\t'

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

trap 'error "Command failed (exit=$?) at ${BASH_SOURCE[0]}:${LINENO}: ${BASH_COMMAND}"' ERR

# Check if running on macOS
check_os() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        error "This script is designed for macOS only"
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."

    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        log "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Ensure brew is on PATH for the current shell session
        if [[ -x /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -x /usr/local/bin/brew ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi

    brew_install() {
        local pkg="$1"
        if ! brew list "$pkg" &> /dev/null; then
            brew install "$pkg"
        fi
    }

    brew_install_cask() {
        local cask="$1"
        if ! brew list --cask "$cask" &> /dev/null; then
            brew install --cask "$cask"
        fi
    }

    brew update

    brew_install git
    brew_install python

    # Docker on macOS typically requires Docker Desktop (cask).
    # Installing CLI utilities is harmless, but the engine is provided by Docker Desktop.
    brew_install_cask docker || true
    brew_install docker || true
    brew_install docker-compose || true
}

# Enhanced setup function
setup_ai_beast() {
    log "Setting up AI Beast environment..."

    # Create necessary directories
    mkdir -p "$HOME/.ai_beast"/{logs,config,scripts,assets,models,backups}

    # Initialize git repo if not exists (best-effort; don't fail if git identity isn't configured)
    if ! git rev-parse --is-inside-work-tree &> /dev/null; then
        git init
        git add . || true
        git commit -m "Initial commit" || warn "Skipping initial commit (git not configured or nothing to commit)"
    fi

    # Set up environment variables
    local env_file="$HOME/.ai_beast/.env"
    if [[ ! -f "$env_file" ]]; then
        cat > "$env_file" << EOF
# AI Beast Environment Variables
AI_BEAST_HOME="$HOME/.ai_beast"
AI_BEAST_LOGS="$HOME/.ai_beast/logs"
AI_BEAST_MODELS="$HOME/.ai_beast/models"
AI_BEAST_ASSETS="$HOME/.ai_beast/assets"
AI_BEAST_CONFIG="$HOME/.ai_beast/config"
AI_BEAST_SCRIPTS="$HOME/.ai_beast/scripts"
EOF
    fi

    # Source environment safely
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a

    log "AI Beast environment setup complete"
}

# Enhanced script management
manage_scripts() {
    log "Managing scripts..."

    # Create main script directory structure
    mkdir -p "$HOME/.ai_beast/scripts"/{core,utils,modules,extensions}

    # Copy existing scripts to new structure (best-effort; don't fail if none exist)
    if [[ -d "scripts" ]]; then
        shopt -s nullglob
        local core_scripts=(scripts/*.sh)
        if (( ${#core_scripts[@]} )); then
            cp "${core_scripts[@]}" "$HOME/.ai_beast/scripts/core/"
        else
            warn "No scripts found in ./scripts to copy"
        fi
        shopt -u nullglob
    else
        warn "No ./scripts directory found; skipping script copy"
    fi

    # Create enhanced script templates
    cat > "$HOME/.ai_beast/scripts/core/ai_beast_main.sh" << 'EOF'
#!/bin/bash

# AI Beast Main Control Script
# This script orchestrates all AI Beast operations

set -e

# Source environment
if [[ -f ~/.ai_beast/.env ]]; then
    set -a
    # shellcheck disable=SC1090
    source ~/.ai_beast/.env
    set +a
fi

# Function to display help
show_help() {
    echo "AI Beast Control Script"
    echo "Usage: ai_beast [command]"
    echo ""
    echo "Commands:"
    echo "  setup          - Initialize AI Beast environment"
    echo "  status         - Show system status"
    echo "  start          - Start AI Beast services"
    echo "  stop           - Stop AI Beast services"
    echo "  restart        - Restart AI Beast services"
    echo "  health         - Run health checks"
    echo "  doctor         - Diagnostic tool"
    echo "  update         - Update AI Beast components"
    echo "  backup         - Create backup"
    echo "  restore        - Restore from backup"
    echo "  help           - Show this help"
    echo ""
}

# Main command dispatcher
case "$1" in
    setup)
        echo "Setting up AI Beast..."
        # Call setup function
        ;;
    status)
        echo "Checking AI Beast status..."
        # Call status function
        ;;
    start)
        echo "Starting AI Beast services..."
        # Call start function
        ;;
    stop)
        echo "Stopping AI Beast services..."
        # Call stop function
        ;;
    restart)
        echo "Restarting AI Beast services..."
        # Call restart function
        ;;
    health)
        echo "Running health checks..."
        # Call health check function
        ;;
    doctor)
        echo "Running diagnostic checks..."
        # Call doctor function
        ;;
    update)
        echo "Updating AI Beast components..."
        # Call update function
        ;;
    backup)
        echo "Creating backup..."
        # Call backup function
        ;;
    restore)
        echo "Restoring from backup..."
        # Call restore function
        ;;
    help)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

EOF

    chmod +x ~/.ai_beast/scripts/core/ai_beast_main.sh
    
    # Create symbolic links for easy access (avoid requiring sudo)
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"
    ln -sf "$HOME/.ai_beast/scripts/core/ai_beast_main.sh" "$bin_dir/ai_beast"
    warn "Installed launcher at: $bin_dir/ai_beast (ensure ~/.local/bin is on your PATH)"
}

# Enhanced configuration management
configure_ai_beast() {
    log "Configuring AI Beast..."
    
    # Create configuration directory
    mkdir -p ~/.ai_beast/config
    
    # Create main configuration file
    cat > ~/.ai_beast/config/ai_beast.conf << 'EOF'
# AI Beast Configuration File
# This file contains all configuration settings for AI Beast

[general]
name = "AI Beast"
version = "1.0.0"
description = "AI/Agent development toolkit for hacking, OSINT, DEFCON, OFFSEC, SIGINT, Surveillance, Counter Offensive, OsInt, hacking, web development, text to image/video/audio/. websearch, code interpretation and running etc."

[paths]
home = "$HOME/.ai_beast"
logs = "$HOME/.ai_beast/logs"
models = "$HOME/.ai_beast/models"
assets = "$HOME/.ai_beast/assets"
config = "$HOME/.ai_beast/config"
scripts = "$HOME/.ai_beast/scripts"

[features]
osint = true
offsec = true
defcon = true
sigint = true
surveillance = true
counter_offensive = true
web_dev = true
media_generation = true
code_interpretation = true
websearch = true

[resources]
max_memory = "32GB"
max_cpu = "100%"
max_disk = "500GB"

[security]
enable_trust = true
enable_audit = true
enable_encryption = true
enable_logging = true

[logging]
level = "INFO"
file = "$HOME/.ai_beast/logs/ai_beast.log"
max_size = "100MB"
max_files = 5

EOF

    log "Configuration complete"
}

# Enhanced health check
health_check() {
    log "Running health checks..."

    # Check system resources (macOS compatible)
    echo "Checking system resources..."
    local mem_bytes
    mem_bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
    if [[ "$mem_bytes" =~ ^[0-9]+$ ]] && (( mem_bytes > 0 )); then
        echo "Memory: $(( mem_bytes / 1024 / 1024 / 1024 )) GB"
    else
        echo "Memory: Unknown"
    fi
    echo "CPU: $(sysctl -n hw.ncpu 2>/dev/null || echo "Unknown") cores"
    echo "Disk: $(df -h / | awk 'NR==2{print $2}')"

    # Check required tools
    echo "Checking required tools..."
    if command -v docker &> /dev/null; then
        echo "Docker CLI: ✓"
    else
        echo "Docker CLI: ✗"
    fi

    if command -v git &> /dev/null; then
        echo "Git: ✓"
    else
        echo "Git: ✗"
    fi

    if command -v python3 &> /dev/null; then
        echo "python3: ✓"
    else
        echo "python3: ✗"
    fi

    log "Health check complete"
}

# Enhanced backup functionality
create_backup() {
    log "Creating backup..."
    
    # Create backup directory
    BACKUP_DIR="$HOME/.ai_beast/backups"
    mkdir -p "$BACKUP_DIR"
    
    # Generate timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_NAME="ai_beast_backup_$TIMESTAMP"
    
    # Create backup archive
    tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
        -C "$HOME/.ai_beast" \
        --exclude='logs' \
        --exclude='backups' \
        .
    
    log "Backup created: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
}

# Enhanced restore functionality
restore_backup() {
    log "Restoring from backup..."
    
    if [[ ! -d "$HOME/.ai_beast/backups" ]]; then
        error "No backups found"
        return 1
    fi
    
    # List available backups
    echo "Available backups:"
    ls -la "$HOME/.ai_beast/backups"
    
    # Prompt for backup selection (simplified)
    echo "Please select a backup to restore (or press Enter for latest):"
    read -r BACKUP_FILE
    
    if [[ -z "$BACKUP_FILE" ]]; then
        BACKUP_FILE=$(ls -t "$HOME/.ai_beast/backups" | head -1)
    fi
    
    if [[ ! -f "$HOME/.ai_beast/backups/$BACKUP_FILE" ]]; then
        error "Backup file not found"
        return 1
    fi
    
    # Restore backup
    echo "Restoring backup: $BACKUP_FILE"
    tar -xzf "$HOME/.ai_beast/backups/$BACKUP_FILE" -C "$HOME/.ai_beast"
    
    log "Restore complete"
}

show_help() {
    cat <<EOF
AI Beast Refactor and Enhancement Script

Usage:
  $(basename "$0") [command]

Commands:
  all (default)  Install deps, setup env, manage scripts, write config, run health checks
  deps           Install dependencies (Homebrew, git, python3, docker tooling)
  setup          Setup AI Beast directories and environment
  scripts        Manage/install AI Beast scripts and launcher
  config         Write default configuration
  health         Run health checks
  backup         Create a backup
  restore        Restore from a backup
  help           Show this help
EOF
}

# Main execution
main() {
    check_os

    local cmd="${1:-all}"
    case "$cmd" in
        all)
            install_dependencies
            setup_ai_beast
            manage_scripts
            configure_ai_beast
            health_check
            log "AI Beast refactoring and enhancement complete!"
            log "Launcher installed as: \$HOME/.local/bin/ai_beast"
            ;;
        deps) install_dependencies ;;
        setup) setup_ai_beast ;;
        scripts) manage_scripts ;;
        config) configure_ai_beast ;;
        health) health_check ;;
        backup) create_backup ;;
        restore) restore_backup ;;
        help|-h|--help) show_help ;;
        *)
            error "Unknown command: $cmd"
            show_help
            return 1
            ;;
    esac
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

: <<'AI_BEAST_TRAILING_JUNK'
# (Disabled) Trailing duplicated content kept only to avoid breaking history; safe to delete.
#!/bin/bash

# AI Beast Refactor and Enhancement Script
# This script refactors and enhances the AI Beast toolkit functionality

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on macOS
check_os() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        error "This script is designed for macOS only"
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        log "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install required packages
    brew install git docker docker-compose python3
}

# Enhanced setup function
setup_ai_beast() {
    log "Setting up AI Beast environment..."
    
    # Create necessary directories
    mkdir -p ~/.ai_beast/{logs,config,scripts,assets,models}
    
    # Initialize git repo if not exists
    if [[ ! -d ".git" ]]; then
        git init
        git add .
        git commit -m "Initial commit"
    fi
    
    # Set up environment variables
    if [[ ! -f ~/.ai_beast/.env ]]; then
        cat > ~/.ai_beast/.env << EOF
# AI Beast Environment Variables
AI_BEAST_HOME=$HOME/.ai_beast
AI_BEAST_LOGS=$HOME/.ai_beast/logs
AI_BEAST_MODELS=$HOME/.ai_beast/models
AI_BEAST_ASSETS=$HOME/.ai_beast/assets
EOF
    fi
    
    # Source environment
    export $(cat ~/.ai_beast/.env | xargs)
    
    log "AI Beast environment setup complete"
}

# Enhanced script management
manage_scripts() {
    log "Managing scripts..."
    
    # Create main script directory structure
    mkdir -p ~/.ai_beast/scripts/{core,utils,modules,extensions}
    
    # Copy existing scripts to new structure
    cp scripts/*.sh ~/.ai_beast/scripts/core/
    
    # Create enhanced script templates
    cat > ~/.ai_beast/scripts/core/ai_beast_main.sh << 'EOF'
#!/bin/bash

# AI Beast Main Control Script
# This script orchestrates all AI Beast operations

set -e

# Source environment
if [[ -f ~/.ai_beast/.env ]]; then
    export $(cat ~/.ai_beast/.env | xargs)
fi

# Function to display help
show_help() {
    echo "AI Beast Control Script"
    echo "Usage: ai_beast [command]"
    echo ""
    echo "Commands:"
    echo "  setup          - Initialize AI Beast environment"
    echo "  status         - Show system status"
    echo "  start          - Start AI Beast services"
    echo "  stop           - Stop AI Beast services"
    echo "  restart        - Restart AI Beast services"
    echo "  health         - Run health checks"
    echo "  doctor         - Diagnostic tool"
    echo "  update         - Update AI Beast components"
    echo "  backup         - Create backup"
    echo "  restore        - Restore from backup"
    echo "  help           - Show this help"
    echo ""
}

# Main command dispatcher
case "$1" in
    setup)
        echo "Setting up AI Beast..."
        # Call setup function
        ;;
    status)
        echo "Checking AI Beast status..."
        # Call status function
        ;;
    start)
        echo "Starting AI Beast services..."
        # Call start function
        ;;
    stop)
        echo "Stopping AI Beast services..."
        # Call stop function
        ;;
    restart)
        echo "Restarting AI Beast services..."
        # Call restart function
        ;;
    health)
        echo "Running health checks..."
        # Call health check function
        ;;
    doctor)
        echo "Running diagnostic checks..."
        # Call doctor function
        ;;
    update)
        echo "Updating AI Beast components..."
        # Call update function
        ;;
    backup)
        echo "Creating backup..."
        # Call backup function
        ;;
    restore)
        echo "Restoring from backup..."
        # Call restore function
        ;;
    help)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

EOF

    chmod +x ~/.ai_beast/scripts/core/ai_beast_main.sh
    
    # Create symbolic links for easy access
    ln -sf ~/.ai_beast/scripts/core/ai_beast_main.sh /usr/local/bin/ai_beast
}

# Enhanced configuration management
configure_ai_beast() {
    log "Configuring AI Beast..."
    
    # Create configuration directory
    mkdir -p ~/.ai_beast/config
    
    # Create main configuration file
    cat > ~/.ai_beast/config/ai_beast.conf << 'EOF'
# AI Beast Configuration File
# This file contains all configuration settings for AI Beast

[general]
name = "AI Beast"
version = "1.0.0"
description = "AI/Agent development toolkit for hacking, OSINT, DEFCON, OFFSEC, SIGINT, Surveillance, Counter Offensive, OsInt, hacking, web development, text to image/video/audio/. websearch, code interpretation and running etc."

[paths]
home = "$HOME/.ai_beast"
logs = "$HOME/.ai_beast/logs"
models = "$HOME/.ai_beast/models"
assets = "$HOME/.ai_beast/assets"
config = "$HOME/.ai_beast/config"
scripts = "$HOME/.ai_beast/scripts"

[features]
osint = true
offsec = true
defcon = true
sigint = true
surveillance = true
counter_offensive = true
web_dev = true
media_generation = true
code_interpretation = true
websearch = true

[resources]
max_memory = "32GB"
max_cpu = "100%"
max_disk = "500GB"

[security]
enable_trust = true
enable_audit = true
enable_encryption = true
enable_logging = true

[logging]
level = "INFO"
file = "$HOME/.ai_beast/logs/ai_beast.log"
max_size = "100MB"
max_files = 5

EOF

    log "Configuration complete"
}

# Enhanced health check
health_check() {
    log "Running health checks..."
    
    # Check system resources
    echo "Checking system resources..."
    echo "Memory: $(free -h | grep Mem | awk '{print $2}')"
    echo "CPU: $(nproc) cores"
    echo "Disk: $(df -h / | tail -1 | awk '{print $2}')"
    
    # Check required services
    echo "Checking required services..."
    if command -v docker &> /dev/null; then
        echo "Docker: ✓"
    else
        echo "Docker: ✗"
    fi
    
    if command -v git &> /dev/null; then
        echo "Git: ✓"
    else
        echo "Git: ✗"
    fi
    
    if command -v python3 &> /dev/null; then
        echo "Python3: ✓"
    else
        echo "Python3: ✗"
    fi
    
    log "Health check complete"
}

# Enhanced backup functionality
create_backup() {
    log "Creating backup..."
    
    # Create backup directory
    BACKUP_DIR="$HOME/.ai_beast/backups"
    mkdir -p "$BACKUP_DIR"
    
    # Generate timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_NAME="ai_beast_backup_$TIMESTAMP"
    
    # Create backup archive
    tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
        -C "$HOME/.ai_beast" \
        --exclude='logs' \
        --exclude='backups' \
        .
    
    log "Backup created: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
}

# Enhanced restore functionality
restore_backup() {
    log "Restoring from backup..."
    
    if [[ ! -d "$HOME/.ai_beast/backups" ]]; then
        error "No backups found"
        return 1
    fi
    
    # List available backups
    echo "Available backups:"
    ls -la "$HOME/.ai_beast/backups"
    
    # Prompt for backup selection (simplified)
    echo "Please select a backup to restore (or press Enter for latest):"
    read -r BACKUP_FILE
    
    if [[ -z "$BACKUP_FILE" ]]; then
        BACKUP_FILE=$(ls -t "$HOME/.ai_beast/backups" | head -1)
    fi
    
    if [[ ! -f "$HOME/.ai_beast/backups/$BACKUP_FILE" ]]; then
        error "Backup file not found"
        return 1
    fi
    
    # Restore backup
    echo "Restoring backup: $BACKUP_FILE"
    tar -xzf "$HOME/.ai_beast/backups/$BACKUP_FILE" -C "$HOME/.ai_beast"
    
    log "Restore complete"
}

# Main execution
main() {
    check_os
    install_dependencies
    setup_ai_beast
    manage_scripts
    configure_ai_beast
    health_check
    
    log "AI Beast refactoring and enhancement complete!"
    log "You can now use: ai_beast [command]"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
EOF

# Make the script executable
chmod +x ai_beast_refactor.sh

# Display usage instructions
echo "AI Beast Refactor and Enhancement Script"
echo "========================================"
echo ""
echo "This script enhances the AI Beast toolkit with:"
echo "1. Better directory structure"
echo "2. Enhanced configuration management"
echo "3. Improved script organization"
echo "4. Better backup/restore functionality"
echo "5. Health checks and diagnostics"
echo ""
echo "To run the refactoring:"
echo "  ./ai_beast_refactor.sh"
echo ""
echo "After running, you can use:"
echo "  ai_beast setup"
echo "  ai_beast status"
echo "  ai_beast start"
echo "  ai_beast stop"
echo "  ai_beast health"
echo "  ai_beast doctor"
echo "  ai_beast backup"
echo "  ai_beast restore"
echo ""
echo "Note: This script will modify your existing AI Beast installation."
echo "Make sure to backup your data before running."
AI_BEAST_TRAILING_JUNK
