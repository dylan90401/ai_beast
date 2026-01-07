# v10 State Reconciler (Terraform-but-for-your-AI-Beast)

This gives you a desired-state file and a reconcile engine that:
- diffs **desired vs actual**
- applies only minimal changes
- is DRYRUN by default

## Files
- Desired state: `config/state.json`
- Example: `config/state.example.json`
- Plan output:
  - `.cache/state.plan.json`
  - `.cache/state.plan.md`

## Commands
Show desired state:
```bash
./bin/beast state show
```

Show discovered actual state:
```bash
./bin/beast state actual
```

Compute a plan:
```bash
./bin/beast state plan
```

Apply the plan:
```bash
./bin/beast state apply --apply
```

Force compose regen/up even if only assets changed:
```bash
./bin/beast state apply --apply --force
```

## Desired State format
```json
{
  "desired": {
    "packs_enabled": ["networking","defsec","media_synth"],
    "extensions_enabled": ["grafana_extra"],
    "asset_packs": [
      {"pack":"sdxl_core","only":"all","strict":true,"rag":false}
    ]
  }
}
```

## Minimal-change logic
- Packs/exts are reconciled as **set equality**
  - anything in desired but not actual => enable
  - anything in actual but not desired => disable
- Assets: installs only missing packs (based on registry presence)
- Compose regen/up runs only if packs/extensions changed (unless `--force`)
