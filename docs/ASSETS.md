# Asset Packs: Models + Workflows (Appliance-grade)

This system installs ComfyUI models and workflows **by pack**, with:
- directory scaffolding
- **sha256 verification**
- optional ClamAV scanning (if installed)
- provenance capture to a registry
- optional registration note for RAG ingestion

## Configure packs
Edit:
- `config/asset_packs.json`

Replace placeholder URLs like:
- `https://huggingface.co/<org>/<repo>/resolve/main/...`

Optionally fill `sha256` for strict verification.

## Install
Dry run:
```bash
./bin/beast assets install sdxl_core
```

Apply:
```bash
./bin/beast assets install sdxl_core --apply
```

Strict allowlist enforcement:
```bash
./bin/beast assets install sdxl_core --apply --strict
```

Install workflows only:
```bash
./bin/beast assets install sdxl_core --apply --only=workflows
```

## Registry output
Written to:
- `DATA_DIR/registry/assets/<pack>/manifest.jsonl`
- `DATA_DIR/registry/assets/<pack>/manifest.md`

## RAG note
A note is written under:
- `DATA_DIR/research/notes/asset_pack_<pack>_<timestamp>.md`

To ingest it automatically:
```bash
./bin/beast assets install sdxl_core --apply --rag
```
