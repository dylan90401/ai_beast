# Python Instructions (beast/, apps/)

### Style & safety
- Use `pathlib.Path`, type hints for public functions.
- Avoid global side effects on import.
- Raise actionable exceptions; never swallow errors.
- Do not hardcode ports/paths: read env derived from `config/paths.env` and `config/ports.env`.

### Process execution
- Centralize subprocess use in `beast/runtime.py` (or repo equivalent).
- Ensure DRYRUN/APPLY gating is respected (prefer plan-first, then execute).

### CLI stability
- Preserve `./bin/beast` UX: subcommands, flags, and output formats are public API.

### Tests
- Prefer pytest. Add small unit tests for config parsing and plan generation.
