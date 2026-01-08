# Build System Instructions (repo-wide)

Goal: guarantee the repo is buildable from a clean checkout.

### Required checks
- `./bin/beast preflight --verbose`
- `docker compose config`
- `shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh`
- `python -m ruff check .`
- `python -m pytest -q`

### Construct-if-missing
If the repo lacks a convenient runner, create/maintain:
- a `Makefile` with targets:
  - `check` (all checks)
  - `lint` (ruff + shellcheck)
  - `fmt` (ruff format)
  - `test` (pytest)
  - `compose-validate` (docker compose config)

If tools are missing, print install hints and continue DRYRUN safely.

### Determinism
- Generated files must be stable (sorted keys, stable formatting).
- Avoid timestamps in generated outputs unless required.
