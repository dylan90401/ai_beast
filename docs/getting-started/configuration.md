# Configuration

AI Beast uses environment files and YAML configuration for flexible setup.

## Configuration Files

| File | Purpose |
|------|---------|
| `config/ai-beast.env` | Main environment variables |
| `config/paths.env` | Directory paths |
| `config/ports.env` | Service ports |
| `config/features.yml` | Feature flags |
| `config/profiles.env` | Resource profiles |

## Environment Configuration

### Main Configuration (`config/ai-beast.env`)

```bash
# AI Beast Environment Configuration

# =============================================================================
# Core Settings
# =============================================================================

# Project name (used for Docker prefixes)
PROJECT_NAME=ai_beast

# Environment: development, staging, production
ENVIRONMENT=development

# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# =============================================================================
# Ollama Settings
# =============================================================================

# Ollama API endpoint
OLLAMA_HOST=http://localhost:11434

# Default model for operations
DEFAULT_MODEL=llama3.2

# Context window size
OLLAMA_NUM_CTX=4096

# Number of parallel requests
OLLAMA_NUM_PARALLEL=2

# =============================================================================
# Vector Database (Qdrant)
# =============================================================================

# Qdrant API endpoint
QDRANT_URL=http://localhost:6333

# Default collection name
QDRANT_COLLECTION=ai_beast

# Embedding dimensions (depends on model)
EMBEDDING_DIM=384

# =============================================================================
# RAG Settings
# =============================================================================

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Chunk size for document splitting
CHUNK_SIZE=512

# Chunk overlap
CHUNK_OVERLAP=50

# Top K results for retrieval
RAG_TOP_K=5

# =============================================================================
# Security
# =============================================================================

# Enable rate limiting
RATE_LIMIT_ENABLED=true

# Requests per minute
RATE_LIMIT_RPM=60

# Enable circuit breaker
CIRCUIT_BREAKER_ENABLED=true

# =============================================================================
# Monitoring
# =============================================================================

# Enable Prometheus metrics
METRICS_ENABLED=true

# Metrics port
METRICS_PORT=9090

# Enable tracing
TRACING_ENABLED=false
```

### Paths Configuration (`config/paths.env`)

```bash
# Directory Paths Configuration

# Base directories
DATA_DIR=${PROJECT_ROOT}/data
MODELS_DIR=${PROJECT_ROOT}/models
OUTPUTS_DIR=${PROJECT_ROOT}/outputs
LOGS_DIR=${PROJECT_ROOT}/logs

# RAG directories
RAG_DOCUMENTS_DIR=${DATA_DIR}/documents
RAG_INDEX_DIR=${DATA_DIR}/index

# Model storage
OLLAMA_MODELS_DIR=${MODELS_DIR}/ollama
HF_CACHE_DIR=${MODELS_DIR}/huggingface

# Temporary files
TEMP_DIR=${PROJECT_ROOT}/tmp
CACHE_DIR=${PROJECT_ROOT}/.cache
```

### Ports Configuration (`config/ports.env`)

```bash
# Service Ports Configuration

# Core services
PORT_DASHBOARD=8080
PORT_OLLAMA=11434
PORT_QDRANT=6333
PORT_REDIS=6379

# Extensions
PORT_OPEN_WEBUI=3000
PORT_N8N=5678
PORT_JUPYTER=8888
PORT_GRAFANA=3001
PORT_PROMETHEUS=9090

# Database
PORT_POSTGRES=5432
```

## Feature Flags

### Features Configuration (`config/features.yml`)

```yaml
# Feature Flags

features:
  # Core features
  dashboard:
    enabled: true
    websocket: true
    auth: false

  rag:
    enabled: true
    parallel_ingest: true
    max_workers: 4

  monitoring:
    enabled: true
    prometheus: true
    grafana: false

  # Security features
  security:
    rate_limiting: true
    circuit_breaker: true
    input_validation: true

  # Extensions
  extensions:
    open_webui: false
    n8n: false
    jupyter: false
    traefik: false

# Resource profiles
profiles:
  default: standard

  minimal:
    ollama_memory: 4G
    qdrant_memory: 1G

  standard:
    ollama_memory: 8G
    qdrant_memory: 2G

  performance:
    ollama_memory: 16G
    qdrant_memory: 4G
```

## Docker Compose Configuration

### Override File (`docker-compose.override.yml`)

Create this file to customize Docker settings:

```yaml
version: "3.8"

services:
  ollama:
    # Use GPU acceleration
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  qdrant:
    # Increase memory
    environment:
      - QDRANT__SERVICE__MAX_QUERY_THREADS=4
```

## Model Configuration

### Model Preferences (`config/model_config.yml`)

```yaml
# Model Configuration

models:
  # Default model settings
  defaults:
    temperature: 0.7
    top_p: 0.9
    top_k: 40
    repeat_penalty: 1.1

  # Per-model overrides
  llama3.2:
    temperature: 0.8
    context_length: 8192
    
  codellama:
    temperature: 0.2
    context_length: 16384

  # Model aliases
  aliases:
    chat: llama3.2
    code: codellama
    fast: phi3:mini
```

## Extension Configuration

Each extension has its own configuration in `extensions/<name>/config.yml`:

```yaml
# extensions/open_webui/config.yml
open_webui:
  enabled: true
  port: 3000
  auth:
    enabled: false
  ollama:
    url: http://ollama:11434
```

## Environment Variables Reference

### Ollama Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_NUM_CTX` | `4096` | Context window size |
| `OLLAMA_NUM_PARALLEL` | `2` | Parallel request limit |
| `OLLAMA_KEEP_ALIVE` | `5m` | Model keep-alive time |

### RAG Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `CHUNK_SIZE` | `512` | Document chunk size |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `RAG_TOP_K` | `5` | Results to retrieve |

### Security Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_RPM` | `60` | Requests per minute |
| `CIRCUIT_BREAKER_ENABLED` | `true` | Enable circuit breakers |
| `CB_FAILURE_THRESHOLD` | `5` | Failures before open |

## Configuration Best Practices

1. **Never commit secrets** - Use `config/secrets/` directory
2. **Use profiles** - Match resources to your hardware
3. **Start minimal** - Enable features as needed
4. **Override locally** - Use `.local` files for personal settings

## Next Steps

- [Model Management](../user-guide/models.md)
- [RAG Configuration](../user-guide/rag.md)
- [Security Settings](../operations/security.md)
