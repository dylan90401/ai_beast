# Installation

This guide covers installing AI Beast on your local machine.

## Prerequisites

- **Python 3.10+** - Required for running AI Beast
- **Docker** - For running containerized services
- **Docker Compose** - For orchestrating multiple containers
- **8GB+ RAM** - Recommended for running LLM models
- **20GB+ Disk Space** - For models and data

### macOS

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.12 docker docker-compose

# Or use Colima for Docker on macOS
brew install colima
colima start --cpu 4 --memory 8 --disk 100
```

### Linux (Ubuntu/Debian)

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3.12 python3.12-venv python3-pip -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y
```

### Windows (WSL2)

```powershell
# Install WSL2 with Ubuntu
wsl --install -d Ubuntu

# Then follow Linux instructions inside WSL
```

## Installation Methods

### Method 1: Quick Start (Recommended)

```bash
# Clone the repository
git clone https://github.com/dylan90401/ai_beast.git
cd ai_beast

# Run bootstrap script
make bootstrap

# This will:
# - Create Python virtual environment
# - Install dependencies
# - Configure environment
# - Pull required Docker images
```

### Method 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/dylan90401/ai_beast.git
cd ai_beast

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Copy environment files
cp config/ai-beast.env.example config/ai-beast.env
cp config/paths.env.example config/paths.env
cp config/ports.env.example config/ports.env

# Start services
docker compose up -d
```

### Method 3: Development Install

```bash
# Clone with full history
git clone https://github.com/dylan90401/ai_beast.git
cd ai_beast

# Install with dev dependencies
pip install -r requirements.txt -r requirements-dev.txt
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Verification

After installation, verify everything is working:

```bash
# Check CLI
beast --version

# Check services
beast status

# Run health check
beast health

# View dashboard
open http://localhost:8080
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started with AI Beast
- [Configuration](configuration.md) - Configure AI Beast for your needs
- [Managing Models](../user-guide/models.md) - Download and manage LLM models
