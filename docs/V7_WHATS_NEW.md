# v7 — Packs Enable + Dependency Graph + Curated ComfyUI Node Bundles

## New commands
Enable packs (toggles + installs deps + installs nodes):
```bash
./bin/beast packs enable <pack> --apply
```

Install node bundle for a pack:
```bash
./bin/beast nodes install --pack=<pack> --apply
```

Strict mode (blocks non-allowlisted repos):
```bash
./bin/beast nodes install --pack=media_synth --apply --strict
```

Doctor:
```bash
./bin/beast doctor
```

One-shot install:
```bash
./bin/beast install --apply
```

## Pack dependency graph
Defined in `config/packs.json` under each pack's `depends`.

## Node allowlist & audits
- Baseline allowlist: `config/comfy_nodes_allowlist.txt`
- Audit includes allowlist check: `./bin/beast audit nodes`
- Strict allowlist check: `./scripts/17_custom_nodes_allowlist_check.sh --strict`
