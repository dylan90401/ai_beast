# Troubleshooting Guide

## Overview

This runbook covers common issues and their solutions for AI Beast.

**Last Updated**: 2025-01-09

---

## Quick Diagnostics

Run these commands to quickly assess system health:

```bash
# Overall status
beast status

# Health check
beast health

# Service logs
beast logs

# System resources
docker stats --no-stream
df -h
free -h
```

---

## Installation Issues

### Python Version Mismatch

**Symptom**: `ModuleNotFoundError` or syntax errors during install

**Solution**:
```bash
# Check Python version
python3 --version

# Must be 3.10 or higher
# If not, install correct version:
# macOS:
brew install python@3.12

# Ubuntu:
sudo apt install python3.12
```

### Dependencies Fail to Install

**Symptom**: `pip install` fails with compilation errors

**Solution**:
```bash
# Install build dependencies
# macOS:
xcode-select --install
brew install cmake

# Ubuntu:
sudo apt install build-essential python3-dev

# Then retry
pip install -r requirements.txt
```

### Docker Not Found

**Symptom**: `docker: command not found`

**Solution**:
```bash
# Install Docker
# macOS with Colima:
brew install colima docker docker-compose
colima start

# macOS with Docker Desktop:
brew install --cask docker

# Ubuntu:
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Log out and back in
```

---

## Service Issues

### Ollama Won't Start

**Symptom**: Ollama container exits immediately or won't respond

**Diagnostic**:
```bash
# Check container status
docker ps -a | grep ollama

# Check logs
docker logs ai_beast_ollama --tail 100
```

**Common Causes and Solutions**:

1. **Port conflict**
   ```bash
   # Check what's using port 11434
   lsof -i :11434
   
   # Stop conflicting process or change port in config/ports.env
   ```

2. **Insufficient memory**
   ```bash
   # Check available memory
   free -h
   
   # Use smaller models
   beast model pull phi3:mini
   ```

3. **Corrupted model**
   ```bash
   # Re-pull model
   beast model rm llama3.2
   beast model pull llama3.2
   ```

### Qdrant Connection Failed

**Symptom**: `Connection refused` to port 6333

**Diagnostic**:
```bash
# Check container
docker ps | grep qdrant

# Check health
curl http://localhost:6333/health

# Check logs
docker logs ai_beast_qdrant --tail 100
```

**Solutions**:
```bash
# Restart container
docker compose restart qdrant

# If data corrupted, recreate
docker compose stop qdrant
docker volume rm ai_beast_qdrant_data
docker compose up -d qdrant
```

### Redis Connection Failed

**Symptom**: Caching not working, slow responses

**Solution**:
```bash
# Check Redis
docker ps | grep redis
docker exec ai_beast_redis redis-cli ping

# Restart if needed
docker compose restart redis
```

---

## Performance Issues

### Slow Response Times

**Diagnostic**:
```bash
# Check system resources
docker stats --no-stream

# Check Ollama response time
time curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3.2","prompt":"Hi","stream":false}'
```

**Solutions**:

1. **Enable caching**
   ```bash
   # Check cache hit rate
   beast cache stats
   
   # Clear cache if needed
   beast cache clear
   ```

2. **Reduce context size**
   ```bash
   # In config/ai-beast.env
   OLLAMA_NUM_CTX=2048  # Reduce from 4096
   ```

3. **Use faster model**
   ```bash
   beast model pull phi3:mini
   ```

### High Memory Usage

**Diagnostic**:
```bash
docker stats --no-stream
```

**Solutions**:
```bash
# Reduce Ollama memory
# In docker-compose.override.yml
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 4G

# Reduce model keep-alive time
# In config/ai-beast.env
OLLAMA_KEEP_ALIVE=1m

# Unload models
curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"llama3.2","keep_alive":0}'
```

### Disk Space Running Low

**Diagnostic**:
```bash
df -h
docker system df
du -sh models/* data/*
```

**Solutions**:
```bash
# Remove unused Docker resources
docker system prune -af

# Remove old logs
find ./logs -name "*.log" -mtime +7 -delete

# Remove unused models
beast model rm unused_model

# Clear RAG cache
rm -rf ./data/cache/*
```

---

## RAG Issues

### Document Ingestion Fails

**Symptom**: `beast rag ingest` errors out

**Diagnostic**:
```bash
# Check Qdrant is running
curl http://localhost:6333/health

# Check disk space
df -h

# Try single file
beast rag ingest ./single_file.pdf -v
```

**Solutions**:

1. **Unsupported file type**
   ```bash
   # Check supported types
   beast rag supported-types
   
   # Convert to supported format
   pandoc input.docx -o output.md
   ```

2. **File too large**
   ```bash
   # Split large files
   split -b 10M large_file.pdf small_
   
   # Or increase chunk size
   # In config/ai-beast.env
   CHUNK_SIZE=1024
   ```

3. **Embedding model error**
   ```bash
   # Clear embedding cache
   rm -rf ./data/embeddings_cache
   
   # Retry
   beast rag ingest ./documents/
   ```

### RAG Queries Return No Results

**Symptom**: Queries return empty results or irrelevant answers

**Diagnostic**:
```bash
# Check collection exists
curl http://localhost:6333/collections

# Check collection has vectors
curl http://localhost:6333/collections/ai_beast
```

**Solutions**:

1. **Wrong collection**
   ```bash
   beast rag query "test" --collection my_collection
   ```

2. **Threshold too high**
   ```bash
   beast rag query "test" --threshold 0.5
   ```

3. **Re-index documents**
   ```bash
   beast rag reindex --collection ai_beast
   ```

---

## Network Issues

### Port Already in Use

**Symptom**: `address already in use` errors

**Solution**:
```bash
# Find process using port
lsof -i :8080

# Kill process
kill -9 PID

# Or change port in config/ports.env
```

### Services Can't Communicate

**Symptom**: Services can't reach each other (e.g., dashboard can't reach Ollama)

**Solution**:
```bash
# Check Docker network
docker network ls
docker network inspect ai_beast_default

# Recreate network
docker compose down
docker network rm ai_beast_default
docker compose up -d
```

---

## Authentication Issues

### Open WebUI Login Failed

**Solution**:
```bash
# Reset Open WebUI
docker compose stop open_webui
docker volume rm ai_beast_open_webui_data
docker compose up -d open_webui

# First login will create new admin
```

### Dashboard Access Denied

**Solution**:
```bash
# Check auth is disabled for local development
# In config/features.yml
dashboard:
  auth: false

# Restart dashboard
make restart-dashboard
```

---

## Extension Issues

### Extension Won't Enable

**Symptom**: `beast extension enable X` fails

**Solution**:
```bash
# Check extension exists
ls extensions/

# Check compose fragment
cat extensions/X/compose.fragment.yaml

# Manual enable
docker compose -f docker-compose.yml \
  -f extensions/X/compose.fragment.yaml up -d
```

### Extension Conflicts

**Symptom**: Services crash after enabling extension

**Solution**:
```bash
# Check for port conflicts
grep -r "ports:" extensions/

# Disable conflicting extension
beast extension disable X

# Check logs
docker logs ai_beast_X --tail 100
```

---

## Getting Help

### Collect Diagnostics

```bash
# Create diagnostic bundle
beast diagnostics > diagnostics.txt

# Or manually:
{
  echo "=== Status ==="
  beast status
  echo "=== Health ==="
  beast health
  echo "=== Docker ==="
  docker ps -a
  docker stats --no-stream
  echo "=== Disk ==="
  df -h
  echo "=== Memory ==="
  free -h
} > diagnostics.txt
```

### Log Locations

| Component | Log Location |
| --------- | ------------ |
| Beast CLI | `./logs/beast.log` |
| Dashboard | `./logs/dashboard.log` |
| Ollama | `docker logs ai_beast_ollama` |
| Qdrant | `docker logs ai_beast_qdrant` |

### Support Resources

- GitHub Issues: https://github.com/dylan90401/ai_beast/issues
- Documentation: https://ai-beast.readthedocs.io/
- Discord: (if available)

---

## Related Runbooks

- [Service Recovery](service-recovery.md)
- [Performance Tuning](performance-tuning.md)
- [Backup and Restore](backup-restore.md)
