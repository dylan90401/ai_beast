# Changelog

All notable changes to AI Beast / Kryptos will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Build System & Infrastructure
- Complete Makefile with targets: check, fmt, lint, test, shellcheck, docker-config, preflight, dev-setup, tools-*, clean, help
- Enhanced pyproject.toml with build-system, dev dependencies, ruff and pytest configuration
- CI/CD workflow (.github/workflows/ci.yml) for automated quality gates
- Smoke tests (tests/test_smoke.py) for buildability verification
- Module integration tests (tests/test_modules.py)
- Requirements files (requirements.txt, requirements-dev.txt)
- Dev environment setup script (scripts/95_dev_setup.sh)

#### Modules
- **modules/monitoring/** - Service health checks and metrics collection
  - `check_service_health()` - Socket-based health verification
  - `collect_metrics()` - System metrics (disk usage, timestamp)
- **modules/security/** - Security scanning and validation
  - `compute_sha256()` - File hashing
  - `verify_file_hash()` - Hash verification
  - `scan_for_secrets()` - Regex-based secret detection
  - `validate_file_permissions()` - Permission checking
- **modules/agent/** - Agent orchestration and state management
  - `AgentState` dataclass - State tracking
  - `AgentOrchestrator` - State persistence and task coordination
- **modules/utils/** - Common utilities
  - `run_command()` - Command execution with output capture
  - `get_base_dir()` - Repository root detection
  - `read_config_file()` - JSON/YAML config parsing
  - `ensure_dir()` - Recursive directory creation
  - `safe_remove()` - Safe file deletion
  - `format_bytes()` - Human-readable byte formatting

#### Tools
- **tools/cli.py** - Command-line utilities
  - `health` command - Service health checks
  - `security` command - Security scanning
  - `diagnostics` command - System diagnostics collection

#### Configuration
- config/ai-beast.env - Main environment configuration
- config/features.env - Generated feature flags (from features.yml)
- GPT-5 Codex Preview feature flag enabled by default
- Agent model default: gpt-5-codex-preview

#### Documentation
- [docs/FEATURE_CATALOG.md](docs/FEATURE_CATALOG.md) - Complete feature inventory with status
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contributor guide
- README updates with tools section and dev setup instructions
- Module-specific README files (monitoring, security, agent, utils)
- tools/README.md

### Changed

- bin/beast - Added env sourcing for ai-beast.env and features.env
- apps/agent/core.py - Updated DEFAULT_MODEL to use FEATURE_AGENT_MODEL_DEFAULT
- apps/agent/kryptos_agent.py - Updated DEFAULT_MODEL resolution
- config/paths.env - Fixed BASE_DIR from hardcoded to actual path
- README.md - Enhanced with build system, tools, and dev setup sections

### Fixed

- scripts/lib/common.sh - Fixed load_env_if_exists() syntax error (shellcheck SC2015)
- bin/beast - Fixed unquoted $MODEL_FLAG variables in agent commands
- config/paths.env - Fixed hardcoded $HOME/AI_Beast/ai_beast/ path

## [19.0.0] - 2024-XX-XX

### Added
- Trust enforcement for assets and workflows (fail-closed by default)
- Backup profiles with optional model/volume inclusion
- Size-aware chunking for large backups

## [18.0.0] - Previous release

(See git history for earlier versions)

---

## Status Legend

- ✅ Complete: Fully implemented and tested
- ⚠️ Partial: Implemented but incomplete or needs enhancement
- ⚠️ Stub: Minimal implementation, needs work
- ❌ Missing: Not yet implemented

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and guidelines.
