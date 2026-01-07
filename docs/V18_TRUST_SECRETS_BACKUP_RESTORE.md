# v18: Trust + Secrets + Backup/Restore (appliance-grade platform layer)

## Secrets (macOS Keychain)
Store secrets in Keychain (service: `ai.beast`) and render to a file for Docker/compose portability.

```bash
echo -n "sk-..." | ./bin/beast secret set OPENAI_API_KEY
./bin/beast secret list
./bin/beast secret render-env
```

Rendered file:
- `config/secrets.rendered.env` (chmod 600)

## Trust (supply-chain posture)
Files:
- `config/resources/trust_policy.json`
- `config/resources/allowlists.json`
- provenance log: `provenance/provenance.db.jsonl`

Run:
```bash
./bin/beast trust report
./bin/beast trust report --apply   # clears macOS quarantine xattrs under workspace (if present)
```

Optional:
- If `trivy` is installed, trust report will scan container images in allowlists.

## Backup / Restore
Backup (portable, restorable snapshot):
```bash
./bin/beast backup --apply
./bin/beast backup --apply --name=my_snapshot
```

Restore:
```bash
./bin/beast restore /path/to/backup.tar.gz --apply
```

By default restore will run:
- `./bin/beast state apply --apply` (if available) to reconcile the restored desired state.

Notes:
- Backups include manifests for models (file lists + sha256), not model blobs by default.
