# Uptime Kuma Extension

Self-hosted service monitoring dashboard.

## Enable

```bash
./bin/beast extensions enable uptime_kuma --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

- URL: `http://127.0.0.1:${PORT_KUMA:-3001}`

## Features

- HTTP/HTTPS monitoring
- TCP port checks
- Ping monitors
- Docker container status
- Status pages
- Notifications (Slack, Discord, Email, etc.)

## Suggested Monitors

Set up monitors for your AI Beast services:

| Service | Type | Target |
|---------|------|--------|
| Ollama | HTTP | `http://host.docker.internal:11434/api/tags` |
| ComfyUI | HTTP | `http://host.docker.internal:8188` |
| Qdrant | HTTP | `http://qdrant:6333/readyz` |
| Open WebUI | HTTP | `http://open-webui:8080/health` |
| n8n | HTTP | `http://n8n:5678/healthz` |
