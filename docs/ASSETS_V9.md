# Assets v9: Lockfiles + Mirrors

## Lockfile (reproducibility)
Generate a lockfile describing your configured asset packs and observed files:
```bash
./bin/beast assets lock --apply
```

Output:
- `config/assets.lock.json`

## Mirror (portable/offline)
Mirror downloads + installed models/workflows + registry to a folder (ideal for external SSD):
```bash
./bin/beast assets mirror --to "/Volumes/YourSSD/AI_Beast_Mirror" --apply
```

## Install using a mirror
```bash
./bin/beast assets install sdxl_core --apply --mirror="/Volumes/YourSSD/AI_Beast_Mirror" --strict
```

Mirror layout created:
- `download/asset_packs/<pack>/...`
- `comfyui/models/...`
- `comfyui/workflows/...`
- `registry/assets/...`
- `config/...`
