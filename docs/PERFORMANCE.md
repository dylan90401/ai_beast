# Performance Best Practices

This document outlines performance optimizations implemented in AI Beast and best practices for maintaining performance.

## File I/O Optimizations

### Chunk-Based File Reading

**Problem**: Reading large files entirely into memory can cause excessive memory usage and slow performance.

**Solution**: Use chunk-based reading for file operations, especially when computing hashes or processing large files.

```python
# ❌ BAD: Loads entire file into memory
with open(file_path, 'rb') as f:
    file_hash = hashlib.sha256(f.read()).hexdigest()

# ✅ GOOD: Processes file in chunks
sha256_hash = hashlib.sha256()
with open(file_path, 'rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        sha256_hash.update(chunk)
file_hash = sha256_hash.hexdigest()
```

**Applied in**:
- `scripts/05_manifest.py`: Manifest generation now uses chunk-based hashing
- `modules/rag/ingest.py`: Added `sha256_file()` function for efficient file hashing

### Benefits
- **Memory**: Constant memory usage regardless of file size (8KB buffer vs potentially GB files)
- **Performance**: Better CPU cache utilization with smaller chunks
- **Scalability**: Can handle arbitrarily large files without OOM errors

## Caching Strategies

### Configuration Caching

**Problem**: Repeated subprocess calls to load environment configuration are expensive (100-200ms per call).

**Solution**: Implement time-based caching with file modification time tracking.

```python
# Cache with TTL and file modification tracking
_cache = None
_cache_mtime = 0
_cache_ttl = 5.0  # seconds

def load_config():
    global _cache, _cache_mtime
    
    # Check if cache is still valid
    current_time = time.time()
    config_mtime = get_config_file_mtime()
    
    if _cache and (current_time - _cache_mtime < _cache_ttl) and config_mtime <= _cache_mtime:
        return _cache
    
    # Load fresh config
    _cache = expensive_load_operation()
    _cache_mtime = current_time
    return _cache
```

**Applied in**:
- `apps/dashboard/dashboard.py`: Environment configuration now cached with 5-second TTL

### Benefits
- **Latency**: Reduces API response time from ~150ms to <1ms for cached hits
- **Load**: Reduces system load from subprocess spawning
- **Consistency**: File modification tracking ensures fresh data when config changes

## Database Connection Pooling

### Existing Implementation

The `modules/db/pool.py` module provides efficient connection pooling for SQLite:

**Features**:
- Connection reuse to reduce overhead
- Automatic idle connection cleanup
- WAL mode for better write concurrency
- Thread-safe operation with minimal locking
- Health checking to remove stale connections

**Usage**:
```python
from modules.db.pool import get_pool

# Get a connection pool
pool = get_pool("data/catalog.db")

# Use with context manager (auto-commit/rollback)
with pool.get_connection() as conn:
    cursor = conn.execute("SELECT * FROM models")
    results = cursor.fetchall()
```

### Best Practices
- Use connection pools instead of opening/closing connections repeatedly
- Keep connections idle for reasonable time (5 min default)
- Monitor pool statistics: `pool.stats()`
- Set appropriate pool sizes based on concurrency needs

## RAG (Retrieval-Augmented Generation) Optimizations

### Batch Processing

**Current Implementation**: The RAG ingestion module processes files in batches of 128 chunks to balance memory usage and API efficiency.

```python
# Flush points in batches
if len(points) >= 128:
    client.upsert(collection_name=collection, points=points)
    points.clear()
```

### Text Chunking

**Strategy**: Overlapping chunks for better context preservation
- Default chunk size: 1200 characters
- Default overlap: 200 characters
- Prevents context loss at chunk boundaries

### Embedding Model Caching

**Implementation**: Singleton pattern for sentence transformer models
- Model loaded once and reused
- Reduces initialization overhead (typically 1-2 seconds per load)

## Runtime Process Execution

### Current Implementation

The `beast/runtime.py` module handles subprocess execution efficiently:

```python
def run(cmd, *, cwd=None, check=True):
    p = subprocess.run(
        list(cmd),
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if check and p.returncode != 0:
        raise RuntimeError(...)
    return CmdResult(p.returncode, p.stdout, p.stderr)
```

### Best Practices
- Use `subprocess.run()` instead of `subprocess.call()` or `subprocess.Popen()` for simple cases
- Always capture output to prevent blocking on pipe buffers
- Use `text=True` to avoid manual encoding/decoding
- Provide clear error messages with stdout/stderr context

## Health Check System

### Parallel Execution

The health checker runs all checks in parallel using `asyncio.gather()`:

```python
results = await asyncio.gather(
    *[checker.check() for checker in checkers],
    return_exceptions=True,
)
```

**Benefits**:
- Total check time is max(individual_check_times) not sum(individual_check_times)
- Typical improvement: 5-10 services checked in ~5s instead of ~25s

### HTTP Timeouts

All HTTP health checks have reasonable timeouts (default 5s):
- Prevents hanging on unresponsive services
- Allows overall health check to complete quickly
- Returns degraded/unhealthy status instead of blocking

## Memory Management

### System Memory Monitoring

The dashboard and health checkers include memory monitoring:
- Tracks total, used, and available memory
- Configurable thresholds for warnings (20%) and critical (10%)
- Platform-specific implementations (macOS via `vm_stat`, Linux via `/proc/meminfo`)

### Best Practices
- Monitor memory usage in long-running processes
- Implement cleanup for idle resources
- Use generators for large datasets instead of loading into memory
- Profile memory usage during development: `python -m memory_profiler script.py`

## Performance Monitoring

### Recommended Tools

**For Development**:
```bash
# Profile CPU usage
python -m cProfile -o profile.stats script.py
python -m pstats profile.stats

# Profile memory usage
pip install memory_profiler
python -m memory_profiler script.py

# Line-by-line profiling
pip install line_profiler
kernprof -l -v script.py
```

**For Production**:
- Use the built-in health check system
- Monitor pool statistics: `pool.stats()`
- Check service response times in health checks
- Review application logs for slow operations

### Metrics to Monitor

1. **Response Times**
   - API endpoints: <100ms for cached, <500ms for DB queries
   - Health checks: <5s total
   - Subprocess calls: <200ms

2. **Resource Usage**
   - Memory: <80% of available
   - Database connections: <50% of pool max
   - File handles: Monitor with `lsof` or system tools

3. **Throughput**
   - RAG ingestion: ~10-50 files/sec depending on size
   - Model downloads: Limited by network bandwidth
   - Batch operations: Monitor completion time trends

## Common Performance Pitfalls

### 1. N+1 Query Problem
```python
# ❌ BAD: N+1 queries
for user_id in user_ids:
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    
# ✅ GOOD: Single query
placeholders = ','.join(['?'] * len(user_ids))
users = db.execute(f"SELECT * FROM users WHERE id IN ({placeholders})", user_ids)
```

### 2. Synchronous I/O in Async Context
```python
# ❌ BAD: Blocking async function
async def get_data():
    result = requests.get(url)  # Blocks event loop
    
# ✅ GOOD: Use async HTTP client
async def get_data():
    async with httpx.AsyncClient() as client:
        result = await client.get(url)
```

### 3. Repeated Configuration Loading
```python
# ❌ BAD: Load on every request
def handler():
    config = load_config_from_disk()  # Expensive
    
# ✅ GOOD: Load once, cache with invalidation
_config = None
def get_config():
    global _config
    if _config is None or config_changed():
        _config = load_config_from_disk()
    return _config
```

### 4. Inefficient String Concatenation
```python
# ❌ BAD: Quadratic time complexity
result = ""
for item in items:
    result += str(item)
    
# ✅ GOOD: Linear time complexity
result = "".join(str(item) for item in items)
```

### 5. Missing Database Indexes
```sql
-- ❌ BAD: Table scan on every query
SELECT * FROM models WHERE name = 'llama2';

-- ✅ GOOD: Add index for frequent queries
CREATE INDEX idx_models_name ON models(name);
```

## Performance Testing

### Before Optimization
Always measure baseline performance before making optimizations:

```python
import time

# Measure execution time
start = time.time()
result = expensive_operation()
duration = time.time() - start
print(f"Operation took {duration:.2f} seconds")
```

### After Optimization
Verify improvements with the same measurement approach:

```python
# Compare multiple runs
import statistics

durations = []
for _ in range(10):
    start = time.time()
    result = optimized_operation()
    durations.append(time.time() - start)

print(f"Average: {statistics.mean(durations):.2f}s")
print(f"Std Dev: {statistics.stdev(durations):.2f}s")
```

## Summary of Optimizations

### Implemented (Current PR)

1. **File Hashing**: Chunk-based reading in manifest generation (8KB chunks)
2. **RAG Ingestion**: Efficient file hashing function for large models
3. **Dashboard Caching**: Config loading cached with 5s TTL and file modification tracking
4. **Documentation**: Performance best practices guide

### Existing (Already in Codebase)

1. **Database Connection Pooling**: Thread-safe pooling with automatic cleanup
2. **Parallel Health Checks**: Async execution for multiple service checks
3. **Lazy Loading**: Embedding models and Qdrant client loaded on demand
4. **Batch Processing**: RAG ingestion processes in 128-chunk batches

### Potential Future Optimizations

1. **Async File I/O**: Use `aiofiles` for async file operations in high-throughput scenarios
2. **Result Caching**: Cache expensive computations (embeddings, model queries)
3. **Request Coalescing**: Combine multiple identical requests into single operation
4. **Lazy Imports**: Import heavy dependencies only when needed
5. **Database Write Batching**: Batch multiple writes into single transaction

## Contributing

When adding new features, consider:

1. **Measure First**: Profile before optimizing
2. **Document Trade-offs**: Explain why you chose this approach
3. **Add Tests**: Include performance regression tests for critical paths
4. **Update This Doc**: Add new patterns and optimizations here
5. **Review Regularly**: Revisit as dependencies and usage patterns evolve
