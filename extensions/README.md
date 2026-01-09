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

Inventory (installed/enabled):
- apache_tika (Docker)
- comfyui_manager (ComfyUI custom node)
- comfyui_video (ComfyUI VideoHelperSuite)
- dify (Docker)
- example_segment / example_service (templates)
- flowise (Docker)
- jupyter (Docker)
- langflow (Docker)
- minio (Docker)
- n8n (Docker)
- open_webui (Docker)
- otel_collector (Docker)
- portainer (Docker)
- postgres (Docker)
- qdrant (Docker)
- redis (Docker)
- searxng (Docker)
- traefik (Docker)
- unstructured_api (Docker)
- uptime_kuma (Docker)
