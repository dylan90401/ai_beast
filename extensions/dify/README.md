# dify

Dockerized Dify stack with API, worker, web UI, Redis, Postgres, and sandbox.

## Notes
- Uses `${DATA_DIR}/dify` for state.
- Default credentials are for local dev only; set real secrets via env vars.
- Requires Qdrant (already part of the base stack) for vector storage.

## Configuration
Environment overrides (optional):
- `DIFY_DB_USER`, `DIFY_DB_PASSWORD`, `DIFY_DB_NAME`
- `DIFY_SECRET_KEY`
- `DIFY_SANDBOX_API_KEY`
