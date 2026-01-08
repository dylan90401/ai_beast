# Bash Instructions (bin/, scripts/)

### Strict mode
- Use `set -euo pipefail` and safe IFS when needed.
- Quote variables; avoid `eval`; avoid parsing `ls`.

### Repo conventions
- Always source `config/paths.env` and `config/ports.env` (or documented generated env).
- Use shared libraries:
  - `scripts/lib/ux.sh` for logging
  - `scripts/lib/deps.sh` for dependency checks
  - `scripts/lib/docker_runtime.sh` for runtime selection
  - `scripts/lib/compose_utils.sh` for compose helpers

### DRYRUN/APPLY
- Default to DRYRUN. Only mutate/install in APPLY.
- In DRYRUN, print the exact commands that WOULD run.

### Lint
- Must pass `shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh`
