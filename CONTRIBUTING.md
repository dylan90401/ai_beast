# Contributing to AI Beast / Kryptos

Welcome! This guide will help you get started with contributing to the project.

## Prerequisites

- macOS (primary platform)
- Python 3.11+ (externally-managed)
- Homebrew (for dependencies)
- Docker (via Colima or Docker Desktop)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/dylan90401/ai_beast.git
cd ai_beast
```

### 2. Run the automated dev setup

```bash
# Option A: Use Makefile
make dev-setup

# Option B: Manual venv setup
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements-dev.txt
pip3 install -r requirements.txt
```

### 3. Verify installation

```bash
make check
```

This will run:
- `ruff format` (code formatting)
- `ruff check` (linting)
- `pytest` (tests)
- `shellcheck` (shell script validation)

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes**
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation

3. **Run quality gates**
   ```bash
   make check
   ```

4. **Test your changes**
   ```bash
   make test
   ./bin/beast preflight
   ```

5. **Commit with descriptive messages**
   ```bash
   git add .
   git commit -m "feat: Add new monitoring feature"
   ```

### Code Style

- **Python**: Follow PEP 8 (enforced by ruff)
  - Line length: 100 characters
  - Use type hints where appropriate
  - Add docstrings for public functions/classes

- **Shell Scripts**: Follow Google Shell Style Guide
  - Use `#!/usr/bin/env bash`
  - Add `set -euo pipefail`
  - Include shellcheck directives as needed
  - Use `scripts/lib/common.sh` for shared utilities

### Testing

```bash
# Run all tests
make test

# Run specific test file
python3 -m pytest tests/test_modules.py -v

# Run with coverage
python3 -m pytest --cov=. --cov-report=html
```

### Documentation

- Update [docs/FEATURE_CATALOG.md](docs/FEATURE_CATALOG.md) for new features
- Add README.md files for new modules/extensions
- Update main [README.md](README.md) for user-facing changes
- Document breaking changes in commit messages

## Project Structure

```
ai_beast/
├── apps/           # Application code (agent, dashboard, speech_api)
├── beast/          # Core runtime and CLI
├── bin/            # CLI entry point (beast)
├── compose/        # Docker Compose files
├── config/         # Configuration files (ports, paths, features, secrets)
├── docs/           # Documentation
├── extensions/     # Optional service extensions
├── modules/        # Python modules (monitoring, security, agent, utils, rag, evaluation)
├── scripts/        # Shell scripts for operations
├── tests/          # Test suite
├── tools/          # CLI tools
└── workflows/      # ComfyUI workflows
```

## Common Tasks

### Adding a New Module

1. Create directory: `modules/my_module/`
2. Add `__init__.py` with implementation
3. Add `README.md` with documentation
4. Add tests in `tests/test_my_module.py`
5. Update [docs/FEATURE_CATALOG.md](docs/FEATURE_CATALOG.md)

### Adding a New Script

1. Create script: `scripts/NN_my_script.sh` (NN = sequence number)
2. Add shebang and set options:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   ```
3. Source common utilities:
   ```bash
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
   source "$SCRIPT_DIR/lib/common.sh"
   ```
4. Implement DRYRUN/APPLY mode support
5. Add to relevant `beast` CLI command
6. Test with `make shellcheck`

### Adding a New Feature Flag

1. Add to [config/features.yml](config/features.yml)
2. Run `./bin/beast features sync --apply`
3. Use in code via `FEATURE_*` environment variables
4. Document in [docs/LIVE_TOGGLES.md](docs/LIVE_TOGGLES.md)

### Adding a New Extension

1. Create directory: `extensions/my_extension/`
2. Add `install.sh` (with DRYRUN support)
3. Add `README.md`
4. Optional: Add `compose.fragment.yaml`
5. Test: `./bin/beast ext install my_extension --dry-run`

## Kryptos Mode Instructions

This repo follows the **Kryptos Directive** for builder-grade engineering:

### Core Principles

1. **DRYRUN by default** - All destructive actions require `--apply`
2. **No hardcoded ports** - Always use `config/ports.env`
3. **No hardcoded paths** - Always use `BASE_DIR` and `config/paths.env`
4. **Minimal diffs** - Small, reversible changes
5. **Evidence-based** - Use repo evidence and command output

### Required Workflow

Every change must follow:

1. **Locate** - Identify affected files
2. **Plan** - ≤6 bullets outlining the change
3. **Patch/Construct** - Make minimal working changes
4. **Prove** - Provide verification commands
5. **Risks + Rollback** - Document edge cases and rollback steps

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for complete details.

## Getting Help

- Check [docs/](docs/) for detailed documentation
- Review [docs/FEATURE_CATALOG.md](docs/FEATURE_CATALOG.md) for feature status
- Run `./bin/beast doctor` for diagnostics
- Run `make tools-diagnostics` for system metrics

## Pull Request Process

1. Ensure all tests pass (`make check`)
2. Update documentation as needed
3. Add clear commit messages
4. Create pull request with description of changes
5. Address review feedback
6. Squash commits if requested

## License

[Add license information here]

## Contact

[Add contact information here]
