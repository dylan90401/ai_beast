# Qdrant Extension

Vector database for RAG (Retrieval-Augmented Generation) workflows.

## Enable

```bash
./bin/beast extensions enable qdrant --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

- HTTP API: `http://127.0.0.1:${PORT_QDRANT:-6333}`
- gRPC API: `127.0.0.1:${PORT_QDRANT_GRPC:-6334}`
- Web UI: `http://127.0.0.1:${PORT_QDRANT:-6333}/dashboard`

## Integration

Used by:
- `modules/rag/ingest.py` for document embedding storage
- Open WebUI for RAG queries (if enabled)
- n8n workflows for vector search

## API Examples

```bash
# Check health
curl http://127.0.0.1:6333/readyz

# List collections
curl http://127.0.0.1:6333/collections

# Create collection
curl -X PUT 'http://127.0.0.1:6333/collections/test' \
  -H 'Content-Type: application/json' \
  -d '{"vectors": {"size": 384, "distance": "Cosine"}}'
```

## Notes

- Data persisted in Docker volume `qdrant_data`
- Supports multiple embedding dimensions
- gRPC port for high-performance clients
