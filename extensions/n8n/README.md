# n8n Extension

Workflow automation platform for AI pipelines and integrations.

## Enable

```bash
./bin/beast extensions enable n8n --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

- URL: `http://127.0.0.1:${PORT_N8N:-5678}`

## Features

- Visual workflow builder
- 400+ integrations
- Webhook triggers
- AI nodes (OpenAI, Ollama, etc.)
- Code nodes (JavaScript, Python)
- Schedule triggers

## Use Cases

- Automate RAG ingestion pipelines
- Connect to external APIs
- Process webhooks
- Schedule tasks
- Chain AI services

## AI Integrations

- Ollama (local LLMs)
- OpenAI / Azure OpenAI
- Anthropic
- Hugging Face
- LangChain

## Storage

- Default: SQLite (in Docker volume)
- Optional: PostgreSQL (enable postgres extension)
