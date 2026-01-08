# Assets & Workflows Instructions (workflows/, config/resources/)

### Workflows
- Keep templates minimal and deterministic.
- Store templates under `workflows/templates/`.
- Validate workflow JSON (basic JSON validation at minimum).

### Assets
- Asset packs are defined in `config/asset_packs.json` and documented in `docs/ASSETS*.md`.
- Any asset installer must honor trust/allowlists and DRYRUN/APPLY.
