# PostgreSQL Extension

Relational database for metadata, state, and structured data.

## Enable

```bash
./bin/beast extensions enable postgres --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

```bash
# CLI
psql -h 127.0.0.1 -p 5432 -U aibeast -d aibeast

# Connection string
postgresql://aibeast:aibeast_dev@127.0.0.1:5432/aibeast
```

## Default Credentials

- User: `aibeast`
- Password: `aibeast_dev`
- Database: `aibeast`

**Change these in production!**

Set via environment variables:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`

## Use Cases

- n8n workflow state
- Langflow/Flowise metadata
- Application state persistence
- RAG document metadata
