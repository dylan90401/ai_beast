# Quick Start

Get up and running with AI Beast in under 5 minutes.

## Start Services

```bash
# Start all core services
make up

# Or start specific services
make up-ollama    # Just Ollama
make up-qdrant    # Just Qdrant vector DB
```

## Download Your First Model

```bash
# Pull a model using the CLI
beast model pull llama3.2

# Or pull a smaller model for testing
beast model pull phi3:mini

# List available models
beast model list
```

## Chat with the Model

### Using the CLI

```bash
# Start interactive chat
beast chat llama3.2

# One-shot generation
beast generate llama3.2 "Explain machine learning in one sentence"
```

### Using Python

```python
from modules.ollama.client import OllamaClient
import asyncio

async def main():
    client = OllamaClient()
    
    # Generate response
    response = await client.generate(
        model="llama3.2",
        prompt="What is the meaning of life?",
    )
    print(response.response)

asyncio.run(main())
```

### Using the Dashboard

1. Open http://localhost:8080 in your browser
2. Navigate to "Chat" in the sidebar
3. Select your model from the dropdown
4. Start chatting!

## Set Up RAG (Document Q&A)

### 1. Ingest Documents

```bash
# Ingest a directory of documents
beast rag ingest ./my-documents/

# Ingest specific file types
beast rag ingest ./docs/ --pattern "*.pdf,*.md"
```

### 2. Query Your Documents

```python
from modules.rag.engine import RAGEngine
import asyncio

async def main():
    engine = RAGEngine()
    
    # Ask a question about your documents
    result = await engine.query(
        "What are the main features of the product?",
        top_k=5,
    )
    
    print("Answer:", result.answer)
    print("Sources:", [s.source for s in result.sources])

asyncio.run(main())
```

## Enable Extensions

AI Beast supports many extensions for additional functionality:

```bash
# Enable Open WebUI (ChatGPT-like interface)
beast extension enable open_webui
make up-open-webui

# Enable n8n (workflow automation)
beast extension enable n8n
make up-n8n

# Enable Jupyter (notebooks)
beast extension enable jupyter
make up-jupyter

# List all extensions
beast extension list
```

## Monitor Services

```bash
# Check service status
beast status

# View logs
beast logs ollama
beast logs qdrant

# Health check
beast health
```

## Common Operations

### Stop Services

```bash
# Stop all services
make down

# Stop specific service
docker compose stop ollama
```

### Update Models

```bash
# Update a specific model
beast model pull llama3.2 --update

# Update all models
beast model update-all
```

### Backup Data

```bash
# Create full backup
./scripts/backup.sh

# Create config-only backup
./scripts/backup.sh -t config
```

## Next Steps

- [Configuration Guide](configuration.md) - Customize AI Beast settings
- [Model Management](../user-guide/models.md) - Learn about model options
- [RAG Pipeline](../user-guide/rag.md) - Build document Q&A systems
- [Extensions](../user-guide/extensions.md) - Add more functionality

## Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker info

# Check for port conflicts
lsof -i :11434  # Ollama
lsof -i :6333   # Qdrant

# View service logs
docker compose logs --tail=50
```

### Model Download Fails

```bash
# Check network connectivity
curl -I https://ollama.ai

# Try direct pull
ollama pull llama3.2

# Check disk space
df -h
```

### Out of Memory

```bash
# Use smaller models
beast model pull phi3:mini
beast model pull gemma2:2b

# Reduce context size in config
# Edit config/ai-beast.env
```

For more troubleshooting, see the [Troubleshooting Guide](../operations/troubleshooting.md).
