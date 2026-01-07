# v15: Typed registries render compose deterministically

v15 makes Compose generation **deterministic** by introducing a typed services registry:

- `config/resources/services.json` → rendered into:
  - `docker/generated/compose.core.yaml`
  - `docker/generated/compose.ops.yaml`

Then:
- `./bin/beast compose gen --apply --mode=state` selects fragments based on desired state,
  but uses the rendered compose as its base/ops input whenever present.

## Render (manual)
```bash
./bin/beast compose render --apply
```

## Generate docker-compose.yml
```bash
./bin/beast compose gen --apply --mode=state
```

## Why this matters
- You can review services in a **single typed catalog**.
- Rendering is reproducible (same input → same compose).
- The graph can treat registry entries as **first-class typed nodes**.
- Adding a new service becomes adding a new record, not hand-editing YAML in multiple places.

## Next
- Extend typed registries for `models.json` and `workflows.json` into the asset installer.
- Render per-service fragments to support ultra-fine minimal updates.
