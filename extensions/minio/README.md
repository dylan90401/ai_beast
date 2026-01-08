# minio

Local S3-compatible artifact store.

- Service name: `minio`
- Default mapping:
  - API: `http://127.0.0.1:${PORT_MINIO}`
  - Console: `http://127.0.0.1:${PORT_MINIO_CONSOLE}`

This service can run when enabled; wiring AI Beast mirrors/manifests is optional.

Secrets:
- Set `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in `config/ai-beast.env` or Keychain-backed env export. Defaults are not recommended.
