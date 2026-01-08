# RAG Module Instructions (modules/rag)

### Goals
- Make ingestion deterministic and safe.
- Respect trust/allowlists when ingesting external docs.
- Avoid hardcoding paths: use `DATA_DIR` derived from `config/paths.env`.

### Interfaces
- Keep `./bin/beast rag ingest ...` stable.
- New backends must be documented and added as packs/extensions if they add services.
