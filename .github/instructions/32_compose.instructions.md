# Compose Instructions (compose/, docker-compose.yml)

### Source of truth
- Compose is assembled from `compose/base.yml` + `compose/packs/*.yml` + extension fragments.
- Generation/render scripts are authoritative: `scripts/25_compose_generate.sh` and `scripts/24_compose_render.sh`.

### Profiles & packs
- Prefer compose profiles for optional services, aligned to `config/resources/pack_services.json`.
- Keep service names stable; pack enabling/disabling should be deterministic.

### Ports & binding
- Never hardcode ports. Use `${PORT_*}` from `config/ports.env`.
- Bind to `127.0.0.1` by default unless user explicitly requests LAN exposure.

### Secrets
- No secrets in compose YAML. Use `.env` or documented placeholders.
- Provide `.env.example` entries for any required vars.

### Validation
- Always run `docker compose config` before `up`.
