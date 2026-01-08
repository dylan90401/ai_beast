# ComfyUI Instructions (native + extensions)

### Rules
- Node installs must be allowlist-driven (`config/comfy_nodes_allowlist.txt`).
- Prefer `scripts/81_comfyui_nodes_install.sh` and `scripts/72_comfyui_postinstall.sh`.
- ComfyUI-Manager integration must be treated as an extension and enforce trust rules.
