# Architecture

This document describes the architecture of AI Beast using the C4 model.

## C4 Model Overview

The [C4 model](https://c4model.com/) provides a hierarchical way to describe
software architecture:

1. **Context** - System and its interactions with users and external systems
2. **Container** - High-level technology choices and containers
3. **Component** - Components within each container
4. **Code** - Implementation details (code level)

## System Context (Level 1)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                           AI Beast                              │
│                   Local AI Infrastructure                       │
│                                                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │   User   │     │  Ollama  │     │ Hugging  │
    │          │     │  Models  │     │   Face   │
    └──────────┘     └──────────┘     └──────────┘
```

### External Systems

| System | Description | Interaction |
|--------|-------------|-------------|
| User | Developers, data scientists | CLI, Dashboard, APIs |
| Ollama Registry | Model repository | Download LLM models |
| Hugging Face | Model hub | Download embedding models |

## Container Diagram (Level 2)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AI Beast                                   │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │    Dashboard    │  │    Beast CLI    │  │   Open WebUI    │         │
│  │    (Quart)      │  │    (Python)     │  │    (Docker)     │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│           └────────────────────┼────────────────────┘                   │
│                                │                                        │
│                    ┌───────────▼───────────┐                            │
│                    │      API Server       │                            │
│                    │       (Python)        │                            │
│                    └───────────┬───────────┘                            │
│                                │                                        │
│           ┌────────────────────┼────────────────────┐                   │
│           │                    │                    │                   │
│  ┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐         │
│  │     Ollama      │  │     Qdrant      │  │     Redis       │         │
│  │    (Docker)     │  │    (Docker)     │  │    (Docker)     │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐                              │
│  │   Prometheus    │  │    Grafana      │                              │
│  │    (Docker)     │  │    (Docker)     │                              │
│  └─────────────────┘  └─────────────────┘                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Containers

| Container | Technology | Purpose |
|-----------|------------|---------|
| Dashboard | Quart (Python) | Web UI for management |
| Beast CLI | Python | Command-line interface |
| Open WebUI | Docker | ChatGPT-like interface |
| API Server | Python | REST API endpoints |
| Ollama | Docker | LLM inference engine |
| Qdrant | Docker | Vector database for RAG |
| Redis | Docker | Caching and queues |
| Prometheus | Docker | Metrics collection |
| Grafana | Docker | Metrics visualization |

## Component Diagram (Level 3)

### Core Modules

```
modules/
├── llm/                    # LLM management
│   ├── manager.py          # Model lifecycle
│   └── manager_async.py    # Async operations
├── ollama/                 # Ollama integration
│   └── client.py           # API client
├── rag/                    # RAG pipeline
│   ├── engine.py           # Query engine
│   ├── chunker.py          # Document chunking
│   └── parallel_ingest.py  # Batch processing
├── security/               # Security components
│   ├── validators.py       # Input validation
│   └── trust.py            # Trust verification
├── resilience/             # Fault tolerance
│   └── circuit_breaker.py  # Circuit breaker pattern
├── ratelimit/              # Rate limiting
│   └── limiter.py          # Token bucket/sliding window
├── health/                 # Health checks
│   └── checker.py          # Service health
├── cache/                  # Caching
│   ├── watcher.py          # File system watcher
│   └── request_cache.py    # LRU cache
├── db/                     # Database
│   └── pool.py             # Connection pooling
├── events/                 # Event system
│   └── bus.py              # Pub/sub events
├── queue/                  # Task queue
│   └── worker.py           # Background jobs
└── monitoring/             # Observability
    └── exporter.py         # Prometheus metrics
```

### Component Interactions

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  LLM Manager │────▶│Ollama Client │────▶│   Ollama     │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │
       │                    ▼
       │            ┌──────────────┐
       │            │Circuit Breaker│
       │            └──────────────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│ Rate Limiter │     │Request Cache │
└──────────────┘     └──────────────┘
```

## Deployment Architecture

### Docker Compose Stack

```yaml
services:
  # Core AI Services
  ollama:       # LLM inference
  qdrant:       # Vector database
  
  # Data Services
  redis:        # Caching
  postgres:     # Metadata storage
  
  # Extensions
  open_webui:   # Web interface
  n8n:          # Workflow automation
  jupyter:      # Notebooks
  
  # Monitoring
  prometheus:   # Metrics
  grafana:      # Dashboards
  
  # Networking
  traefik:      # Reverse proxy
```

### Port Mapping

| Service | Internal Port | External Port |
|---------|---------------|---------------|
| Dashboard | 8080 | 8080 |
| Ollama | 11434 | 11434 |
| Qdrant | 6333 | 6333 |
| Redis | 6379 | 6379 |
| Open WebUI | 3000 | 3000 |
| Prometheus | 9090 | 9090 |
| Grafana | 3001 | 3001 |

## Data Flow

### RAG Pipeline

```
Document Ingestion:
  Documents → Chunker → Embeddings → Qdrant

Query Processing:
  Query → Embeddings → Qdrant Search → Context → LLM → Response
```

### Request Flow

```
User Request
     │
     ▼
┌─────────┐     ┌─────────────┐     ┌──────────┐
│ Traefik │────▶│ Rate Limiter│────▶│ API      │
└─────────┘     └─────────────┘     └──────────┘
                                          │
                      ┌───────────────────┼───────────────────┐
                      │                   │                   │
                      ▼                   ▼                   ▼
               ┌──────────┐        ┌──────────┐        ┌──────────┐
               │  Cache   │        │  Ollama  │        │  Qdrant  │
               └──────────┘        └──────────┘        └──────────┘
```

## Security Architecture

### Defense Layers

1. **Input Validation** - Path traversal, URL validation
2. **Rate Limiting** - Token bucket, sliding window
3. **Circuit Breakers** - Prevent cascade failures
4. **Health Checks** - Proactive monitoring

### Security Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                       Public Network                         │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │    Traefik      │  ◄── TLS termination
                    │  (Reverse Proxy)│  ◄── Rate limiting
                    └────────┬────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│                    Internal Network                          │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Dashboard│  │  Ollama  │  │  Qdrant  │  │  Redis   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Generating Diagrams

To generate PNG diagrams from the diagram definitions:

```bash
# Install diagrams library
pip install diagrams

# Generate all diagrams
python docs/architecture/diagrams.py

# Diagrams saved to docs/architecture/images/
```

## References

- [C4 Model](https://c4model.com/)
- [Diagrams Library](https://diagrams.mingrammer.com/)
- [Architecture Decision Records](./decisions/)
