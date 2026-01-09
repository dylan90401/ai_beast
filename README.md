# AI Beast Starter (Kryptos) — v19 Trust-Enforced Assets + Chunked Backup/Restore

**Native guts + user-selectable storage + optional Docker services + local dashboard + extensible extensions.**
**v19 adds:** Trust enforcement wired into asset/workflow installs (fail-closed), plus backup profiles with optional model/volume inclusion and size-aware chunking.


## Quick start

```bash
# 1) Configure (or run the wizard)
cp config/paths.env.example config/paths.env
cp config/ports.env.example config/ports.env
cp config/profiles.env.example config/profiles.env
cp config/ai-beast.env.example config/ai-beast.env

# 2) Optional: interactive wizard (recommended)
./bin/beast init --apply

# 3) Preflight
./bin/beast preflight

# 4) Bootstrap (DRYRUN then APPLY)
./bin/beast bootstrap --dry-run
./bin/beast bootstrap --apply

# 5) Start
./bin/beast up
./bin/beast dashboard   # local control panel UI
```

## Build System

This repo is buildable via standard targets:

```bash
# Run all checks (format, lint, test, shellcheck)
make check

# Individual targets
make fmt          # Format Python code with ruff
make lint         # Lint Python code with ruff
make test         # Run pytest
make shellcheck   # Check shell scripts

# Validation
make docker-config  # Validate docker compose
make preflight      # Run beast preflight

# Clean
make clean        # Remove Python cache files
```

### Installing dev dependencies

```bash
# Option 1: Automated dev setup (recommended)
make dev-setup

# Option 2: Manual setup with pipx (for externally-managed Python)
brew install pipx
pipx install ruff
pipx install pytest

# Option 3: Manual setup with venv
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements-dev.txt

# Install shellcheck for shell script linting
brew install shellcheck
```

## Tools

The repo includes command-line tools for operations and diagnostics:

```bash
# Check service health
make tools-health
# Or directly: python3 tools/cli.py health

# Run security checks (secret scanning, permissions)
make tools-security
# Or directly: python3 tools/cli.py security

# Collect diagnostics (metrics, disk usage, etc.)
make tools-diagnostics
# Or directly: python3 tools/cli.py diagnostics
```

See [tools/README.md](tools/README.md) and [docs/FEATURE_CATALOG.md](docs/FEATURE_CATALOG.md) for complete feature inventory.

## Workspace Evaluation

Evaluate workspace health, configuration, and services:

```bash
# Run all evaluations
./bin/beast eval

# Run specific category
./bin/beast eval --category system
./bin/beast eval --category docker
./bin/beast eval --category config
./bin/beast eval --category extensions

# Output formats
./bin/beast eval --format text   # Human-readable (default)
./bin/beast eval --format json   # Machine-readable

# Save report
./bin/beast eval --save .cache/evaluation-report.txt
./bin/beast eval --format json --save .cache/evaluation-report.json
```

See [modules/evaluation/README.md](modules/evaluation/README.md) for detailed documentation.

## launchd auto-start (optional, macOS)

```bash
./bin/beast launchd --apply
# later:
./bin/beast launchd --unload --apply
```

## Extensions

Drop in `extensions/<name>/install.sh` (DRYRUN default).
```bash
./bin/beast ext list
./bin/beast ext install example_service --dry-run
./bin/beast ext install example_service --apply
```

## Compose generation (extensions)

```bash
./bin/beast compose gen --dry-run
./bin/beast compose gen --apply
```

This merges:
- docker/compose.yaml
- docker/compose.ops.yaml
- extensions/**/compose.fragment.yaml

into **docker/compose.generated.yaml** using `docker compose ... config`.

## Workflows + audits

```bash
./bin/beast workflows install --apply
./bin/beast audit nodes
./bin/beast model scan "$CACHE_DIR/downloads" --apply
```


## v5 additions: features + storage split + RAG + smoke tests

Initialize with internal **guts** + external **heavy**:
```bash
./bin/beast init --apply --heavy-dir=/Volumes/SSD/AI_Beast_Heavy --guts-dir=/path
./bin/beast features sync --apply
```

Post-install ComfyUI (symlink models to heavy storage + seed workflows):
```bash
./bin/beast comfy postinstall --apply
```

RAG ingest (Qdrant must be running):
```bash
./bin/beast up
source "$VENV_DIR/bin/activate"
pip3 install -r modules/rag/requirements.txt
./bin/beast rag ingest --dir "$DATA_DIR/inbox" --collection ai_beast --apply
```

Smoke tests:
```bash
./bin/beast smoke
```

## Post-install feature packs

```bash
./bin/beast packs list
./bin/beast packs install osint defsec media_synth --apply
./bin/beast compose gen --apply
./bin/beast up
```

## v7 Packs (deps + ComfyUI bundles)

```bash
./bin/beast packs list
./bin/beast packs enable media_synth --apply
./bin/beast compose gen --apply
./bin/beast up
./bin/beast doctor
```

## v8 Asset Packs (models + workflows)

```bash
./bin/beast assets list
./bin/beast assets install sdxl_core --apply --strict
```

## v9 Live Toggles + Extensions

```bash
./bin/beast live status
./bin/beast live enable media_synth --apply
./bin/beast extensions list
```

## v9 Assets: lock + mirror

```bash
./bin/beast assets lock --apply
./bin/beast assets mirror --to "/Volumes/External/AI_Beast_Mirror" --apply
```

## v10 State Reconciler (desired-state)

```bash
cp config/state.example.json config/state.json
./bin/beast state plan
./bin/beast state apply --apply
```

## v11 Graph + Drift

```bash
./bin/beast graph
./bin/beast drift status
./bin/beast drift apply --apply
```

## speech_stack (STT/TTS)

```bash
./bin/beast packs install speech_stack --apply
./bin/beast speech up
curl -s http://127.0.0.1:${PORT_SPEECH_API:-9977}/health | jq
```


## v13: Typed graph + explainable plans

- `./bin/beast graph typed` emits a fully typed resource graph with stable node IDs.
- `./bin/beast state plan` now also emits:
  - `.cache/typed_graph.json|md|dot`
  - `.cache/plan.reasoned.json|md`
- Asset installs append to a global provenance log:
  - `$DATA_DIR/provenance/provenance.db.jsonl`

## v15: Typed compose registry

```bash
./bin/beast compose render --apply
./bin/beast compose gen --apply --mode=state
```

## Trust enforcement

Asset/workflow installs now **fail closed by default** against `config/resources/trust_policy.json`
and `config/resources/allowlists.json`.

```bash
# enforce (default): fails closed if SHA/provenance/tier rules are violated
./bin/beast assets install --pack=sdxl_core --apply

# warn-only mode (still records provenance)
./bin/beast assets install --pack=sdxl_core --trust=warn --apply

# disable trust checks (not recommended)
./bin/beast assets install --pack=sdxl_core --trust=off --apply

# inspect quarantine + basic trust report
./bin/beast trust report
```

## Backup & restore (profiles + chunking)

Backups are manifest-driven and can optionally include large model/workflow blobs and Docker volumes.

```bash
# snapshot (workspace + registry/provenance)
./bin/beast backup --profile=standard --apply

# include model/data blobs, chunk into 2GB parts (portable/offline moves)
./bin/beast backup --profile=full --chunk-size=2g --apply

# appliance-grade: include docker volumes too
./bin/beast backup --profile=appliance --chunk-size=2g --with-volumes --apply

# restore (runs state reconcile by default)
./bin/beast restore "$BACKUP_DIR/<backup-folder>" --apply

# restore without reconciler
./bin/beast restore "$BACKUP_DIR/<backup-folder>" --no-reconcile --apply
```


## v20: Trust tiers + mirrors + signed manifests (optional)

- Tightened trust defaults: ComfyUI nodes default to **official-only**; models default to **vendor/author/official**.
- New trust modes: `./bin/beast trust mode nodes official_only|community_ok --apply` (same for models/manifests).
- New mirror registry: `config/resources/mirrors.json` (supports sha256-path mirrors + prefix-replace mirrors).
- New manifest signing: `./bin/beast manifest sign|verify ...` using OpenSSH `ssh-keygen -Y`.
- Asset installs can now **fail closed** when signatures are required (toggle via trust mode).
