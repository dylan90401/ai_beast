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

## Quickstart (macOS)
```bash
cp -n config/ports.env.example config/ports.env
cp -n config/ai-beast.env.example .env
./bin/beast preflight --verbose
./bin/beast bootstrap
./scripts/25_compose_generate.sh
./scripts/24_compose_render.sh
docker compose config
docker compose up -d
docker compose ps
```

## Buildable definition
- `./bin/beast preflight --verbose`
- `docker compose config`
- `shellcheck -x bin/* scripts/*.sh scripts/lib/*.sh`
- `python -m ruff check .`
- `python -m pytest -q`

## Self-healing contract
If required pieces are missing, construct excellent versions following repo patterns:
- Makefile targets (`check`, `lint`, `fmt`, `test`, `compose-validate`)
- `.env.example` only (no real secrets)
- pack/extension stubs (disabled by default)
- shared helpers only when repeated references exist
Stubs must be explicit: `TODO(KRYPTOS): <acceptance criteria>`.
