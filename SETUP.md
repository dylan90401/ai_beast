# AI Beast / Kryptos Setup Guide

## Quick Setup

### 1. Apply Critical Patches

```bash
# Fix 82_assets.sh duplication (removes duplicate lines 1047-1243)
bash scripts/patch_82_assets.sh

# Verify the fix
make shellcheck 2>&1 | grep -c "SC2218"  # Should be 0
```

### 2. Install Development Dependencies

```bash
# Option A: Automated setup (recommended)
make dev-setup

# Option B: Manual with venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Option C: Manual with pipx (CLI tools only)
brew install pipx
pipx install ruff
pipx install pytest
```

### 3. Verify Installation

```bash
# Run all quality gates
make check

# Expected: format, lint, and test all run successfully
# Shellcheck will show warnings but no critical errors
```

## What Was Added

### Python Modules

1. **modules/evaluation/evaluator.py** - Evaluation framework with metrics
2. **modules/agent/agent_runner.py** - Agent execution and response collection
3. **modules/monitoring/tracer.py** - Distributed tracing with OTEL support
4. **modules/security/** - Already complete (hash verification, secret scanning)
5. **modules/utils/** - Already complete (common utilities)

### CLI Tools

- **tools/cli.py** - Health checks, security scans, diagnostics
- **beast/cli.py** - Python CLI with evaluation and agent commands

### Tests

- **tests/test_evaluator.py** - Evaluation module tests
- **tests/test_agent_runner.py** - Agent runner tests
- **tests/test_cli.py** - CLI tests
- **tests/test_modules.py** - Already complete (integration tests)
- **tests/test_smoke.py** - Already complete (smoke tests)

### Configuration

- **config/ai-beast.env** - Main environment config
- **config/features.env** - Generated feature flags
- **pyproject.toml** - Updated with dependencies and package metadata
- **requirements.txt** - Core dependencies (pyyaml, requests)
- **requirements-dev.txt** - Dev dependencies (ruff, pytest, pytest-cov)

### Scripts

- **scripts/patch_82_assets.sh** - Fixes 82_assets.sh duplication
- **scripts/95_dev_setup.sh** - Automated dev environment setup
- **scripts/13_trust.sh** - Fixed heredoc syntax errors

### Documentation

- **docs/FEATURE_CATALOG.md** - Complete feature inventory
- **CONTRIBUTING.md** - Contributor guide
- **CHANGELOG.md** - Version history
- **SETUP.md** - This file

## Running Tests

```bash
# Run all tests
make test

# Run specific test file
python3 -m pytest tests/test_evaluator.py -v

# Run with coverage
python3 -m pytest --cov=modules --cov=beast --cov-report=html
```

## Using Python CLI

```bash
# Show status
python3 -m beast.cli status

# Run evaluation (requires test dataset)
python3 -m beast.cli eval --test-dataset data/test.jsonl --output results.json

# Run agent on test dataset
python3 -m beast.cli agent test_dataset.jsonl --output agent_results.jsonl
```

## Using Tools

```bash
# Check service health
python3 tools/cli.py health

# Run security checks
python3 tools/cli.py security

# Collect diagnostics
python3 tools/cli.py diagnostics
```

## Build System

```bash
# Format code
make fmt

# Lint code
make lint

# Run tests
make test

# Check shell scripts
make shellcheck

# Validate docker compose
make docker-config

# Run preflight checks
make preflight

# Run all checks
make check
```

## Known Issues

### Shellcheck Warnings

After applying patches, there are ~150 shellcheck warnings remaining across scripts. These are non-critical:

- **SC2034** - Unused variables (often used externally or in sub-shells)
- **SC2015** - `A && B || C` patterns (intentional for DRYRUN/APPLY logic)
- **SC2027/SC2086** - Quote warnings (mostly in DRYRUN log messages)
- **SC1091** - Can't follow sourced files (expected for generated/optional files)
- **SC2012/SC2011** - Use find instead of ls (low priority refactor)

These don't block functionality and can be addressed incrementally.

### Python 3.14 Externally Managed

macOS Homebrew Python 3.14 is externally managed. Solutions:

1. **Use venv** (recommended): `python3 -m venv .venv && source .venv/bin/activate`
2. **Use pipx** (for CLI tools): `brew install pipx && pipx install <package>`
3. **Use make dev-setup**: Automates the setup process

### Missing Config Files

Some scripts expect config files that are generated on first run:

- `config/ports.env` - Copy from `config/ports.env.example`
- `config/profiles.env` - Copy from `config/profiles.env.example`

Run `./bin/beast init --apply` to generate all required config files.

## Next Steps

1. **Setup development environment**: `make dev-setup`
2. **Run quality gates**: `make check`
3. **Initialize config**: `./bin/beast init --apply`
4. **Start services**: `./bin/beast up`
5. **Run smoke tests**: `./bin/beast smoke`

## Troubleshooting

### Import Errors

If Python can't find modules:

```bash
# Install in editable mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="$PWD:$PYTHONPATH"
```

### Test Failures

If tests fail due to missing dependencies:

```bash
# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Shellcheck Errors After Patching

If critical errors remain:

```bash
# Check patch was applied
wc -l scripts/82_assets.sh  # Should show 1046 lines

# If not, manually apply
sed -i.bak '1047,$d' scripts/82_assets.sh
```

## Getting Help

- **Docs**: See [docs/](docs/) directory for detailed documentation
- **Feature Catalog**: [docs/FEATURE_CATALOG.md](docs/FEATURE_CATALOG.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Diagnostics**: Run `./bin/beast doctor` or `make tools-diagnostics`
