# langflow

Adds a Langflow container via a compose fragment with persistent storage.

Enable via:

```bash
./bin/beast packs install agent_builders --apply
./bin/beast ext enable langflow --apply
./bin/beast compose gen --apply
./bin/beast up --apply
```

## Configuration
- Data stored in `${DATA_DIR}/langflow`.
