# minio (stub)

Local S3-compatible artifact store.

- Service name: `minio`
- Default mapping:
  - API: `http://127.0.0.1:${PORT_MINIO}`
  - Console: `http://127.0.0.1:${PORT_MINIO_CONSOLE}`

This is "stub" in the sense that we are not yet wiring AI Beast mirrors/manifests to store artifacts in MinIO. The service itself is real and can run when enabled.

Secrets:
- Set `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in `config/ai-beast.env` or Keychain-backed env export. Defaults are not recommended.
