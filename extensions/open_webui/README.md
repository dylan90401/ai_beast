# Open WebUI Extension

ChatGPT-style interface for local LLMs via Ollama.

## Enable

```bash
./bin/beast extensions enable open_webui --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

- URL: `http://127.0.0.1:${PORT_WEBUI:-3000}`

## Features

- Chat with Ollama models (connects to native Ollama)
- RAG with Qdrant integration
- Web search (optional)
- Code highlighting
- Model switching
- Conversation history

## Requirements

- Ollama running natively (port 11434)
- Optional: Qdrant extension for RAG

## Configuration

Environment variables in compose.fragment.yaml:
- `OLLAMA_BASE_URL`: Ollama API endpoint
- `WEBUI_AUTH`: Set to "true" to require login
- `RAG_EMBEDDING_MODEL`: Model for document embeddings
