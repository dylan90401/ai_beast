# Security / Trust Instructions (assets, models, nodes)

Trust/allowlists:
- `config/model_sources_allowlist.txt`
- `config/workflow_sources_allowlist.txt`
- `config/comfy_nodes_allowlist.txt`

Trust scripts:
- `scripts/13_trust.sh`, `scripts/14_trust_enforce_asset.sh`
- audits: `scripts/15_*`, `scripts/16_*`

### Rules
- Do not add new model/workflow/node sources without updating allowlists.
- Any ingestion of external artifacts should verify provenance (hash/signature if available).
- Support DRYRUN everywhere.

### Never
- Never auto-download unverified models in APPLY without explicit intent.
