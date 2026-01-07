# Extensions

Each extension lives in `extensions/<name>/`.

Required:
- `install.sh`  (DRYRUN default; supports `--apply`; idempotent)

Optional:
- `compose.fragment.yaml`
  - Included automatically when you run:
    - `./bin/beast compose gen --apply`
  - And `./bin/beast up` will auto-generate + prefer `docker/compose.generated.yaml`.

Rules:
- Never hardcode paths. Source `config/paths.env`.
- Keep compose fragments focused (one feature/service group).

- comfyui_manager: installs ComfyUI-Manager custom node

## Newly added stub extensions
- dify (stub)
- apache_tika (stub)
- unstructured_api (stub)
- otel_collector (minimal)
- minio (minimal)
