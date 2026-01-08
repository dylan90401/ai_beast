# Repo Map & Conventions (AI Beast)

Use this repo’s real structure. If anything differs, discover it first.

### Entry points
- `./bin/beast` (shell wrapper) → `beast/cli.py` (argparse) → `beast/runtime.py` (process execution)

### Compose system
- Base: `compose/base.yml`
- Packs: `compose/packs/*.yml`
- Generate: `scripts/25_compose_generate.sh`
- Render: `scripts/24_compose_render.sh`
- Validate: `docker compose config` (always before `up`)

### Config sources
- Paths: `config/paths.env` (BASE_DIR + derived roots)
- Ports: `config/ports.env` (PORT_*)
- Features: `config/features.yml`
- Packs registry: `config/packs.json`
- Services/pack map: `config/resources/services.json`, `config/resources/pack_services.json`

### Shell libraries (use these; don’t duplicate)
- UX/logging: `scripts/lib/ux.sh`
- deps: `scripts/lib/deps.sh`
- docker runtime selection: `scripts/lib/docker_runtime.sh`, `scripts/lib/docker.sh`
- compose helpers: `scripts/lib/compose_utils.sh`
