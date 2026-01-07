# v17: Clean compose generation + compose profile graph + surgical drift

## Compose generation (fixed)
- `./bin/beast compose gen --apply --mode=state`
  - Computes desired services from packs + extension fragments
  - Renders base/ops from `config/resources/services.json` (subset for desired services)
  - Selects fragments and writes `.cache/compose.selection.json`
  - Writes `docker-compose.yml` and `.cache/compose.fingerprint.json`

- `./bin/beast compose render --apply`
  - Renders from typed registry (optionally subset via `--only-services=a,b,c`)
  - Adds deterministic labels:
    - `ai.beast.managed=true`
    - `ai.beast.service_hash=<sha256>`
    - `ai.beast.profiles=<profiles...>`
  - Writes `.cache/compose.service_hashes.json`

## Typed graph improvements
- Pack → Service edges via `config/resources/pack_services.json`
- Service → Profile edges via `config/resources/services.json`

This enables drift to explain **why** a service exists.

## Drift (surgical)
- `./bin/beast drift status`
  - Missing / Stopped / Hash drift / Extra
- `./bin/beast drift apply --apply`
  - Creates only missing services
  - Restarts only stopped services
  - Recreates only drifted services (`--force-recreate`)
  - Optionally removes extras (default on)
