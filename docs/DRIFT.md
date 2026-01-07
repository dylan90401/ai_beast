# v11 Drift Detection (compose)

Shows differences between:
- desired services (from compose config)
- running containers (compose project label)

Commands:
```bash
./bin/beast drift status
./bin/beast drift apply --apply
```

Notes:
- If your docker compose supports `--dry-run`, we attempt to detect which services would be recreated.
- Apply path targets only changed/missing services first, then optionally removes orphans.
