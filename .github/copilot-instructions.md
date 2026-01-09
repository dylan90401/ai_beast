# Copilot Instructions — AI Beast / Kryptos (Repo-Specific, Builder-Grade)

You are an engineering agent working inside this repo. Your mission is to keep the workspace **buildable**, **runnable**, **portable**, and **safe**.
Optimize for: Truth > Tone | Precision > Verbosity | Reproducibility > vibes.

## Non‑negotiables
- **DRYRUN by default.** Any state-changing action requires explicit APPLY mode and must be stated.
- **No hardcoded ports.** Always source/read `config/ports.env` and use `PORT_*`.
- **No hardcoded paths.** Always anchor to `BASE_DIR` and read `config/paths.env`.
- **Minimal diffs.** Prefer small, reversible changes; include rollback steps.
- **No secrets in git.** Use `.env` / Keychain / documented placeholders.

## Repo reality (don’t guess; verify paths)
- CLI: `./bin/beast` → Python entry `beast/cli.py` + `beast/runtime.py`
- Compose system: `compose/base.yml` + `compose/packs/*.yml` + generation scripts:
  - `scripts/25_compose_generate.sh` (generate)
  - `scripts/24_compose_render.sh` (render)
- Packs/registry: `config/packs.json`, `config/resources/pack_services.json`, `beast/registry.json`
- Features: `config/features.yml` (and generated env file if used)
- Extensions: `extensions/*/compose.fragment.yaml` + `extensions/*/install.sh`
- Agents: `apps/agent/` (pipelines, playbooks, prompts)

## Definition of done (must satisfy)
When your changes touch code/config/compose, your result must pass:
1) `./bin/beast preflight --verbose`
2) `docker compose config` (or the rendered compose output if that is the repo’s standard)
3) `shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh`
4) `python -m ruff check .`
5) `python -m pytest -q`

If a check is not applicable (e.g., docker not installed), you must:
- state the reason,
- provide install hints,
- still ensure deterministic output and safe DRYRUN behavior.

## Required workflow (always)
1) **Locate**: cite files/entry points you will touch.
2) **Plan**: ≤ 6 bullets; include verification commands.
3) **Patch**: smallest change; preserve CLI UX unless asked.
4) **Prove**: provide commands + expected results.
5) **Rollback**: explain how to revert.

## Construct-if-missing (you may create missing pieces)
If required artifacts are missing/broken, you may create minimal correct versions:
- Makefile targets (`check`, `lint`, `fmt`, `test`, `compose-validate`)
- `.env.example` (never real secrets)
- pack/extension compose fragments (stubbed, disabled)
- missing helper scripts under `scripts/lib/` only if referenced by multiple scripts

Stubs must be explicit: `TODO(KRYPTOS): <acceptance criteria>` and safe in DRYRUN.

## UX and logging
- Prefer existing logging helpers: `scripts/lib/ux.sh`.
- Maintain consistent `[ai-beast]` or `[KRYPTOS]` style prefixes if present.
- Avoid changing output text unless asked (tools/tests may depend on it).

## Asking for evidence
Ask for **one** missing output at a time:
- `./bin/beast --help`
- `./bin/beast preflight --verbose`
- `docker compose config`
- last ~80 lines of `./bin/beast logs <service> -f`

## Output format (in chat)
1) Summary
2) Plan
3) Files changed/added
4) Commands to run
5) Expected results
6) Risks / edge cases
7) Rollback
