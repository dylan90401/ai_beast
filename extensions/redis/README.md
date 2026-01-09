# Redis Extension

In-memory cache and message broker.

## Enable

```bash
./bin/beast extensions enable redis --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

- Redis CLI: `redis-cli -h 127.0.0.1 -p ${PORT_REDIS:-6379}`

## Use Cases

- Session caching
- Rate limiting
- Message queues
- Temporary data storage

## Configuration

- Max memory: 512MB (configurable)
- Eviction policy: allkeys-lru
- Persistence: AOF enabled
