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

## Project-specific patterns & quick checks
- Centralize subprocess/process execution in `beast/runtime.py` (prefer this over ad-hoc subprocess calls).
- Shell scripts: use helpers in `scripts/lib/` (`ux.sh`, `deps.sh`, `compose_utils.sh`) and implement DRYRUN vs APPLY.
- Compose generation merges `docker/compose.yaml`, `docker/compose.ops.yaml`, and `extensions/**/compose.fragment.yaml` → validate with `docker compose -f docker/compose.generated.yaml config`.
- Asset/trust: `assets install` is governed by `config/resources/trust_policy.json` and `config/resources/allowlists.json` (may fail-closed by default).
- Useful verification commands to include in PRs:
  - `make check` (format + lint + tests + shellcheck)
  - `./bin/beast preflight --verbose`
  - `docker compose -f docker/compose.generated.yaml config`
  - `./bin/beast smoke` (if applicable)
  - `./bin/beast eval --format json --save .cache/eval.json`
- Tests: add pytest unit tests under `tests/`; add small integration / smoke tests for CLI changes.
- Files to consult: `README.md`, `CONTRIBUTING.md`, `.github/instructions/*.md`, `beast/cli.py`, `beast/runtime.py`.


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

## App-specific notes (quick reference)
- apps/dashboard:
  - Dashboard is the central WebUI control panel at `apps/dashboard/` exposing all capabilities, tools, packs, extensions, and settings.
  - All security tools (OSINT, SIGINT, OFFSEC, DEFCOM) are accessible through dashboard UI with LLM integration.
  - Tool catalog (`config/resources/tool_catalog.json`) and capabilities (`config/resources/capabilities.json`) are auto-rendered.
  - Dashboard binds to `PORT_DASHBOARD` (default 8787) and requires token auth (`config/secrets/dashboard_token.txt`).
  - API endpoints: `/api/tools/*`, `/api/capabilities`, `/api/llm/analyze` for LLM integration.
- apps/comfyui:
  - ComfyUI installs often involve symlinking models into heavy storage and running `./bin/beast comfy postinstall --apply` to seed workflows. Check `apps/comfyui/ComfyUI` README and `extensions/comfyui_manager/` for manager helpers.
  - Model files and workflows live under `apps/comfyui/ComfyUI/user/` and may be large — prefer `--heavy-dir` or external volumes when testing locally.
- apps/agent:
  - Agent playbooks and prompts are in `apps/agent/playbooks/` and `apps/agent/prompts/` — preserve the `DRYRUN` pattern when changing automated flows.
  - Observability hooks: `modules/monitoring/tracer.py` and `modules/agent/agent_runner.py` set up tracing; include trace file or logs when proving agent behavior.
- apps/whispercpp (and other model tooling):
  - Model conversion scripts and README live under `apps/whispercpp/whisper.cpp/`; include model conversion commands in docs when changing model handling.
- modules/rag:
  - RAG ingestion expects qdrant running; include `pip install -r modules/rag/requirements.txt` and `./bin/beast rag ingest --apply` in verification steps.
- Security Tools (OSINT/SIGINT/OFFSEC/DEFCOM):
  - All security capabilities are defined in `config/resources/capabilities.json` with 200+ tools catalogued.
  - Tool registry: `modules/tools/registry.py` manages tool lifecycle (install, test, run).
  - Capability registry: `modules/capabilities/registry.py` validates and checks capability health.
  - Dashboard exposes all tools with LLM-assisted execution (`/api/llm/analyze` for guidance).
  - See `.github/instructions/94_security_tools.instructions.md` for detailed security tool integration.

## CI & verification guidance
- There are no committed workflow files in this repo root; if your PR will introduce or expect CI workflows, include a minimal GitHub Actions YAML and ensure it runs `make check` and any relevant `./bin/beast` validations.
- Recommended CI steps for PRs affecting infra/runtime:
  - Checkout + setup Python (`python -m venv .venv && source .venv/bin/activate`) and install dev deps
  - make check
  - ./bin/beast preflight --verbose
  - docker compose -f docker/compose.generated.yaml config (or equivalent validate step)
  - Run smoke/integration tests (e.g., `./bin/beast smoke` or `pytest -q tests/<target>`)
- Attach failing logs or a short snippet (last ~80 lines) when reporting CI or runtime failures.

## PR checklist for agents (copy into PR description)
- Brief summary & rationale
- Plan (≤ 6 bullets) and list of files changed
- Verification commands to reproduce locally
  - `make check`
  - `./bin/beast preflight --verbose`
  - `docker compose -f docker/compose.generated.yaml config`
- Tests added (unit + any small integration/smoke tests)
- Evidence: CI green or local `make check` + `preflight` outputs attached
- Risk assessment & rollback steps
- Ensure no secrets or hardcoded ports/paths are committed
- If modifying runtime/compose: include `docker compose config` output in PR

---
Please tell me any app-specific behaviors or CI steps you'd like emphasized and I'll incorporate them.