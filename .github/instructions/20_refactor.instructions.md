# Refactoring Instructions

## Refactoring contract (behavior-preserving unless requested)
- Prefer incremental refactors (small units), not mega rewrites.
- Keep public surfaces stable: CLI flags, env var names, service names, output formats.
- Extract helpers only when duplication exists in ≥2 places.
- Add/adjust tests or assertions to lock behavior.
- Finish with verification (see repo DoD).

### Preferred refactor targets in this repo
- Consolidate dependency checks in `scripts/lib/deps.sh` (used by bootstrap/preflight).
- Consolidate docker runtime selection in `scripts/lib/docker_runtime.sh`.
- Ensure `./bin/beast` subcommands map cleanly to `scripts/*` and `beast/*.py`.
- Keep compose generation/render logic centralized (do not fork ad-hoc compose commands).
