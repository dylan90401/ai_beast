# v8 — Appliance-grade Asset Installer

## New command
```bash
./bin/beast assets list
./bin/beast assets show sdxl_core
./bin/beast assets install sdxl_core --apply [--strict] [--rag] [--only=models|workflows|all]
```

## What it does
- Downloads model/workflow files into `DOWNLOAD_DIR/asset_packs/<pack>/`
- Verifies SHA256 if provided (always computes and logs)
- Optionally ClamAV scans if installed
- Installs into:
  - Models: `COMFYUI_MODELS_DIR/<subdir>/...`
  - Workflows: `COMFYUI_WORKFLOWS_DIR/...` (prefers ComfyUI user workflows)
- Captures provenance in a pack registry under `DATA_DIR/registry/assets/<pack>/`
- Writes a RAG note under `DATA_DIR/research/notes/` and can ingest it with `--rag`
