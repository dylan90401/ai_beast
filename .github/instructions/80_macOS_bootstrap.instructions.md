# macOS Bootstrap Instructions (scripts/20_bootstrap_macos.sh)

### Dependency management
- Use `scripts/lib/deps.sh` for checks and install hints.
- Respect DRYRUN/APPLY.
- Honor `DOCKER_RUNTIME` selection and runtime helpers.

### Invariants
- Never write outside `BASE_DIR`.
- Never assume fixed install paths; detect Homebrew prefix.
