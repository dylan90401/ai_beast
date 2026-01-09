# Jupyter (Code Runner)

This extension runs JupyterLab for interactive notebooks and code execution.

Service:
- JupyterLab on `PORT_JUPYTER` (default `8889`)

Config:
- `AI_BEAST_JUPYTER_TOKEN` (set in `config/ai-beast.env`)

Install:
```bash
./bin/beast extensions install jupyter --apply
./bin/beast compose gen --apply
./bin/beast up
```
