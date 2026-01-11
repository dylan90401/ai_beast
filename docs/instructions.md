# AI Beast / Kryptos — Instructions (Buildable + Self-Healing)

This repo is designed to be:
- Portable (anchored to `BASE_DIR`)
- Safe (DRYRUN default; explicit APPLY)
- Composable (base compose + packs + extensions)
- Buildable (quality gates + deterministic generation)
- Self-healing (agents can construct missing parts safely)

## Golden rules
- DRYRUN by default; APPLY only with explicit intent.
- Never hardcode ports: `config/ports.env` (`PORT_*`).
- Never hardcode paths: `BASE_DIR` + `config/paths.env`.
- Prefer minimal diffs; always include rollback steps.
- Prefer `.venv` and run tools via `./.venv/bin/python -m ...` (fallback: `python3`).
- All shell scripts must include `set -euo pipefail` for safety.

## Quickstart (macOS)
```bash
# 1. Copy configuration templates
cp -n config/ports.env.example config/ports.env
cp -n config/paths.env.example config/paths.env
cp -n config/ai-beast.env.example config/ai-beast.env
cp -n config/profiles.env.example config/profiles.env

# 2. Install development dependencies
make dev-setup
# OR manually:
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install -r requirements-dev.txt

# 3. Run preflight checks
./bin/beast preflight --verbose

# 4. Bootstrap environment (macOS dependencies)
./bin/beast bootstrap --apply

# 5. Generate compose files
./bin/beast compose gen --apply

# 6. Validate and start
docker compose config
./bin/beast up --apply

# 7. Check status
./bin/beast status
```

## Buildable definition

The project must pass all quality gates:

```bash
# Run all checks
make check

# Individual checks
make preflight        # System dependencies and configuration
make compose-validate # Docker Compose syntax
make lint            # Ruff linting + shellcheck
make test            # Pytest suite
make fmt             # Code formatting (ruff)
```

Required passing commands:
- `./bin/beast preflight --verbose`
- `docker compose config` (no errors)
- `shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh`
- `./.venv/bin/python -m ruff check .`
- `./.venv/bin/python -m pytest -q`

## Self-healing contract

If required pieces are missing, construct excellent versions following repo patterns:
- Makefile targets (`check`, `lint`, `fmt`, `test`, `compose-validate`)
- `.env.example` only (no real secrets)
- pack/extension stubs (disabled by default)
- shared helpers only when repeated references exist

Stubs must be explicit: `TODO(KRYPTOS): <acceptance criteria>`.

## Critical Requirements

### 1. Dependency Management
- **Python version:** Requires Python 3.12+ (see pyproject.toml)
- **Package manager:** Use pip or pipx for Python packages
- **Virtual environments:** Always use venv or pipx for isolation
- **Status:** requirements.txt dependency typo (`quartc` → `quart`) fixed

### 2. Security Requirements
- **Path traversal protection:** Always use `Path.resolve()` before file operations
- **Input validation:** Validate all user inputs, especially URLs and file paths
- **Secret management:** Use macOS Keychain via `scripts/12_secrets_keychain.sh`
- **Trust enforcement:** Asset/workflow installs fail-closed by default (config/resources/trust_policy.json)
- **SHA256 verification:** All downloads must verify hashes before use
- **Allowlists:** Custom nodes and models must be on allowlists (config/comfy_nodes_allowlist.txt, config/model_sources_allowlist.txt)

### 3. Code Quality Standards
- **Type hints:** All public functions must have type annotations
- **Docstrings:** All modules, classes, and public functions need docstrings
- **Error handling:** Use consistent error patterns (raise or return error dict, not mixed)
- **Logging:** Use structured logging (prefer logging module over print statements)
- **Testing:** Minimum 60% test coverage required (currently <10%)
- **Cyclomatic complexity:** Maximum 10 per function

### 4. Architecture Patterns
- **Dependency injection:** Pass dependencies explicitly, avoid globals
- **Async I/O:** Use asyncio for network operations
- **Event-driven:** Prefer event bus over imperative chaining
- **Immutability:** Use dataclasses with frozen=True for value objects
- **Separation of concerns:** Keep I/O, business logic, and presentation separate

### 5. Configuration Management
- **Environment variables:** Load from config/ai-beast.env and config/features.env
- **Feature flags:** Use config/features.yml for toggles
- **No hardcoded values:** All paths, ports, and URLs must be configurable
- **Validation:** Validate all configuration on load
- **Defaults:** Provide sensible defaults for all optional config

### 6. Docker Compose Generation
- **Multi-layer composition:** base.yml → packs/*.yml → extensions/*/compose.fragment.yaml
- **State-driven:** Use config/state.json for desired state
- **Validation:** Always validate with `docker compose config` before apply
- **Rendering:** Use scripts/24_compose_render.sh for final rendering
- **Metadata:** Store generation metadata in docker/generated/compose.render.meta.json

### 7. Extension System
- **Structure:** extensions/<name>/{README.md, install.sh, compose.fragment.yaml}
- **Install script:** Must support --dry-run and --apply modes
- **Idempotent:** Can run multiple times safely
- **Composable:** Fragments merge cleanly with base compose
- **Documentation:** README must document ports, volumes, and dependencies

### 8. Testing Requirements
- **Unit tests:** tests/test_*.py for all modules
- **Integration tests:** tests/integration/ for workflows
- **Property tests:** Use Hypothesis for generative testing
- **Smoke tests:** tests/test_smoke.py for basic sanity
- **Fixtures:** Use pytest fixtures for reusable test data
- **Mocking:** Mock external dependencies (network, filesystem, docker)
- **Coverage:** Run with `pytest --cov=. --cov-report=html`

### 9. Performance Guidelines
- **Caching:** Cache expensive operations (file scans, API calls)
- **Invalidation:** Use file watchers or TTL for cache invalidation
- **Parallel processing:** Use ProcessPoolExecutor for CPU-bound work
- **Async operations:** Use asyncio for I/O-bound work
- **Database:** Use SQLite for metadata storage (not JSON files)
- **Streaming:** Stream large files, don't load into memory
- **Batch operations:** Batch database/API operations

### 10. Observability
- **Logging:** Structured logs with context (model_name, operation, duration)
- **Metrics:** Export Prometheus metrics (counters, histograms, gauges)
- **Tracing:** OpenTelemetry traces for distributed operations
- **Health checks:** All services expose /health endpoints
- **Status reporting:** `./bin/beast status` shows comprehensive status

## Module Guidelines

### modules/agent/
- Agent orchestration and state management
- State persistence in config/agent_state.json
- Task execution with tool loops
- Multi-agent pipelines in apps/agent/pipelines/

### modules/evaluation/
- Workspace evaluation framework
- System health, Docker services, configuration, extensions
- Report generation (JSON and text formats)
- Metrics: pass/fail/warn/skip status

### modules/llm/
- LLM model manager (Ollama + local files)
- Model scanning, downloading, deletion
- Storage info and location management
- Ollama API integration

### modules/rag/
- RAG ingestion for Qdrant vector store
- Text chunking and embedding
- Batch and single-file ingestion
- Sentence-transformers integration

### modules/security/
- SHA256 hashing and verification
- Secret scanning (regex-based)
- File permission validation
- Trust policy enforcement

### modules/monitoring/
- Service health checks (socket-based)
- Metrics collection (disk usage, timestamps)
- System diagnostics

### modules/utils/
- Common utilities (command execution, config parsing)
- Base directory detection
- Safe file operations
- Byte formatting

## Script Conventions

### Naming
- `NN_<name>.sh` where NN is sequence number (00-99)
- Use descriptive names: `25_compose_generate.sh` not `compose.sh`

### Structure
```bash
#!/usr/bin/env bash
set -euo pipefail

# Script purpose description
# Usage: ./script.sh [--apply] [args...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source common utilities
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

# Parse arguments
APPLY_MODE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --apply) APPLY_MODE=true; shift ;;
    *) die "Unknown option: $1" ;;
  esac
done

# Main logic
if [[ "$APPLY_MODE" == "true" ]]; then
  # Actual changes
  info "Applying changes..."
else
  # Dry run
  info "DRY RUN: Would apply changes..."
fi
```

### Required Elements
- Shebang: `#!/usr/bin/env bash`
- Safety: `set -euo pipefail`
- Directory detection: Use `SCRIPT_DIR` and `BASE_DIR`
- Common utilities: Source `lib/common.sh`
- Argument parsing: Support `--apply` flag
- Dry-run default: Show what would happen without --apply
- Error handling: Use `die()` function for errors
- Logging: Use `info()`, `warn()`, `error()` functions

## Python Module Structure

### Module Template
```python
"""Module description.

Longer description of the module's purpose and functionality.
"""

from __future__ import annotations  # Enable postponed annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MyClass:
    """Class description."""

    field: str
    optional_field: int = 0

    def method(self, arg: str) -> dict[str, Any]:
        """Method description.

        Args:
            arg: Argument description

        Returns:
            Return value description

        Raises:
            ValueError: When validation fails
        """
        if not arg:
            raise ValueError("arg must not be empty")

        return {"status": "ok", "value": arg}


def module_function(path: Path, apply: bool = False) -> dict[str, Any]:
    """Function description.

    Args:
        path: Path to process
        apply: Whether to apply changes (default: dry-run)

    Returns:
        Dict with 'ok' and optional 'error' keys
    """
    if not path.exists():
        return {"ok": False, "error": f"Path not found: {path}"}

    if not apply:
        logger.info("DRY RUN: Would process %s", path)
        return {"ok": True, "dryrun": True}

    # Actual processing
    logger.info("Processing %s", path)
    return {"ok": True}
```

## Common Patterns

### Configuration Loading
```python
from pathlib import Path
import os

def load_config() -> dict[str, str]:
    """Load configuration from environment and config files."""
    base_dir = Path(os.getenv("BASE_DIR", Path.cwd()))
    config_file = base_dir / "config" / "ai-beast.env"

    config = {}
    if config_file.exists():
        for line in config_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip().strip('"').strip("'")

    return config
```

### Safe File Operations
```python
from pathlib import Path
import shutil

def safe_delete(path: Path, allowed_parents: list[Path]) -> dict[str, Any]:
    """Safely delete a file with parent directory validation.

    Args:
        path: File to delete
        allowed_parents: List of allowed parent directories

    Returns:
        Dict with 'ok' and optional 'error' keys
    """
    # Resolve to prevent symlink/traversal attacks
    resolved = path.resolve()

    # Validate path is under allowed parents
    if not any(resolved.is_relative_to(p) for p in allowed_parents):
        return {"ok": False, "error": "Path not in allowed directories"}

    if not resolved.exists():
        return {"ok": False, "error": "File not found"}

    try:
        resolved.unlink()
        return {"ok": True, "path": str(resolved)}
    except OSError as e:
        return {"ok": False, "error": str(e)}
```

### Async Operations
```python
import asyncio
import aiohttp
from pathlib import Path

async def download_async(url: str, destination: Path) -> dict[str, Any]:
    """Download a file asynchronously.

    Args:
        url: URL to download from
        destination: Local file path

    Returns:
        Dict with 'ok', 'size_bytes', and optional 'error' keys
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                if resp.status != 200:
                    return {"ok": False, "error": f"HTTP {resp.status}"}

                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(destination, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Progress callback here

                return {"ok": True, "size_bytes": downloaded}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

## Troubleshooting

### Preflight Failures
```bash
# Check system dependencies
./bin/beast preflight --verbose

# Common issues:
# - Python < 3.12: Install newer Python
# - Docker not running: Start Docker/Colima
# - Missing configs: Copy from .example files
# - Port conflicts: Edit config/ports.env
```

### Test Failures
```bash
# Run specific test
python3 -m pytest tests/test_modules.py::test_name -v

# Debug mode
python3 -m pytest tests/test_modules.py -v --pdb

# Show print statements
python3 -m pytest tests/test_modules.py -v -s
```

### Docker Compose Issues
```bash
# Validate syntax
docker compose config

# Regenerate compose files
./bin/beast compose gen --apply

# Check specific service
docker compose logs <service_name> -f

# Rebuild container
docker compose up -d --force-recreate <service_name>
```

### Agent Errors
```bash
# Check agent state
cat config/agent_state.json | jq

# Verify agent setup
./scripts/17_agent_verify.sh

# Reset agent state
rm config/agent_state.json
./scripts/15_agent_setup.sh --apply
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines on:
- Development workflow
- Code style requirements
- Testing requirements
- Pull request process
- Kryptos directive principles

## Security

### Reporting Vulnerabilities
Report security issues to: [Add contact method]

### Known Issues
1. Path traversal in modules/llm/manager.py:456 (fix in progress)
2. Command injection risk in shell scripts (audit in progress)
3. Insufficient input validation for URLs (fix in progress)

### Security Checklist
- [ ] All user inputs validated
- [ ] No hardcoded secrets (use Keychain)
- [ ] SHA256 verification for downloads
- [ ] Path operations use .resolve()
- [ ] Trust policy enforced
- [ ] Allowlists checked
- [ ] Secrets scanning enabled

## Performance Optimization

### Recommended Settings
```bash
# config/ai-beast.env
CACHE_TTL_SECONDS=300
MAX_PARALLEL_DOWNLOADS=4
EMBEDDING_BATCH_SIZE=128
DATABASE_POOL_SIZE=10
```

### Profiling
```bash
# Profile Python code
python3 -m cProfile -o profile.stats scripts/script.py
python3 -m pstats profile.stats

# Memory profiling
python3 -m memory_profiler scripts/script.py

# Benchmark
python3 -m pytest tests/benchmarks/ --benchmark-only
```

## Maintenance

### Regular Tasks
```bash
# Update dependencies
pip install -U -r requirements.txt

# Clean cache
make clean

# Vacuum database
sqlite3 "$DATA_DIR/provenance/provenance.db" "VACUUM;"

# Rotate logs
find logs/ -name "*.log" -mtime +30 -delete

# Backup
./bin/beast backup --profile=full --apply
```

### Monitoring
```bash
# Check service health
./bin/beast status

# Collect diagnostics
make tools-diagnostics

# Check disk usage
df -h "$HEAVY_DIR"

# Monitor resource usage
docker stats
```

## License

[Add license information]

## Support

- Documentation: docs/
- Feature Catalog: docs/FEATURE_CATALOG.md
- Issues: [Add issue tracker URL]
- Discussions: [Add discussion forum URL]
