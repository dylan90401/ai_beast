# Service Recovery Runbook

## Overview

This runbook covers procedures for recovering AI Beast services from various failure states.

**Severity**: P0 (Critical)  
**Time to Complete**: 5-30 minutes depending on failure type  
**Last Updated**: 2025-01-09

## Prerequisites

- SSH access to the host machine
- Docker and Docker Compose installed
- Access to backup storage (if data recovery needed)
- Basic understanding of AI Beast architecture

## Quick Reference

| Symptom | Action |
| ------- | ------ |
| All services down | [Full Stack Recovery](#full-stack-recovery) |
| Ollama unresponsive | [Ollama Recovery](#ollama-recovery) |
| Qdrant unavailable | [Qdrant Recovery](#qdrant-recovery) |
| Dashboard not loading | [Dashboard Recovery](#dashboard-recovery) |
| Out of memory | [Memory Recovery](#memory-recovery) |
| Disk full | [Disk Recovery](#disk-recovery) |

---

## Full Stack Recovery

### Symptoms
- All services unreachable
- `beast status` shows all services as down
- Docker daemon may be unresponsive

### Procedure

1. **Check Docker daemon**
   ```bash
   # Check if Docker is running
   docker info
   
   # If not running, start Docker
   # macOS with Colima:
   colima start
   
   # Linux:
   sudo systemctl start docker
   ```

2. **Check for zombie containers**
   ```bash
   # List all containers including stopped
   docker ps -a
   
   # Remove any stuck containers
   docker compose down --remove-orphans
   ```

3. **Clean up and restart**
   ```bash
   cd /path/to/ai_beast
   
   # Full cleanup
   make clean-docker
   
   # Restart all services
   make up
   ```

4. **Verify recovery**
   ```bash
   # Check status
   beast status
   
   # Health check
   beast health
   ```

### Verification
- [ ] All services show "running" in `beast status`
- [ ] Health checks pass
- [ ] Dashboard accessible at http://localhost:8080
- [ ] Can generate text with `beast generate llama3.2 "test"`

---

## Ollama Recovery

### Symptoms
- Chat/generate commands fail
- "Connection refused" errors to port 11434
- High CPU/memory usage on ollama container

### Procedure

1. **Check Ollama status**
   ```bash
   # Check if container is running
   docker ps | grep ollama
   
   # Check logs
   docker logs ai_beast_ollama --tail 100
   ```

2. **Restart Ollama**
   ```bash
   # Graceful restart
   docker compose restart ollama
   
   # Wait for startup (30 seconds)
   sleep 30
   
   # Verify
   curl http://localhost:11434/api/tags
   ```

3. **If restart doesn't work**
   ```bash
   # Stop container
   docker compose stop ollama
   
   # Remove container (preserves data)
   docker compose rm -f ollama
   
   # Recreate
   docker compose up -d ollama
   ```

4. **Check model availability**
   ```bash
   # List models
   beast model list
   
   # Re-pull if needed
   beast model pull llama3.2
   ```

### Verification
- [ ] `curl http://localhost:11434/api/tags` returns JSON
- [ ] `beast model list` shows expected models
- [ ] `beast generate llama3.2 "Hello"` works

---

## Qdrant Recovery

### Symptoms
- RAG queries fail
- "Qdrant unavailable" errors
- Vector search returns no results

### Procedure

1. **Check Qdrant status**
   ```bash
   # Check container
   docker ps | grep qdrant
   
   # Check logs
   docker logs ai_beast_qdrant --tail 100
   
   # Check API
   curl http://localhost:6333/health
   ```

2. **Restart Qdrant**
   ```bash
   docker compose restart qdrant
   
   # Verify health
   curl http://localhost:6333/health
   ```

3. **If data corruption suspected**
   ```bash
   # Stop Qdrant
   docker compose stop qdrant
   
   # Backup current data (if recoverable)
   cp -r ./data/qdrant ./data/qdrant_backup
   
   # Clear and restart
   docker compose up -d qdrant
   
   # Re-ingest documents if needed
   beast rag ingest ./documents/
   ```

### Verification
- [ ] `curl http://localhost:6333/health` returns `{"title": "Ok"}`
- [ ] Collections visible: `curl http://localhost:6333/collections`
- [ ] RAG queries work: `beast rag query "test"`

---

## Dashboard Recovery

### Symptoms
- Dashboard not loading at http://localhost:8080
- WebSocket connection errors
- Static assets not loading

### Procedure

1. **Check if dashboard is running**
   ```bash
   # Check process
   ps aux | grep dashboard
   
   # Check port
   lsof -i :8080
   ```

2. **Restart dashboard**
   ```bash
   # If running as service
   make restart-dashboard
   
   # Or manually
   pkill -f dashboard
   cd apps/dashboard && python app.py &
   ```

3. **Check configuration**
   ```bash
   # Verify environment
   cat config/ai-beast.env | grep DASHBOARD
   
   # Check static files exist
   ls -la apps/dashboard/static/
   ```

### Verification
- [ ] http://localhost:8080 loads
- [ ] No console errors in browser
- [ ] Real-time updates working (if WebSocket enabled)

---

## Memory Recovery

### Symptoms
- Services killed by OOM killer
- "Cannot allocate memory" errors
- System becomes unresponsive

### Procedure

1. **Identify memory consumer**
   ```bash
   # Check container memory usage
   docker stats --no-stream
   
   # Check system memory
   free -h
   ```

2. **Free memory immediately**
   ```bash
   # Stop non-essential services
   docker compose stop grafana prometheus n8n jupyter
   
   # Reduce Ollama memory
   docker compose stop ollama
   docker compose up -d ollama  # Will use new limits
   ```

3. **Adjust memory limits**
   ```bash
   # Edit docker-compose.override.yml
   cat > docker-compose.override.yml << 'EOF'
   version: "3.8"
   services:
     ollama:
       deploy:
         resources:
           limits:
             memory: 4G
     qdrant:
       deploy:
         resources:
           limits:
             memory: 1G
   EOF
   
   # Apply changes
   docker compose up -d
   ```

4. **Use smaller models**
   ```bash
   # Remove large models
   beast model rm llama3.2:70b
   
   # Use smaller alternatives
   beast model pull phi3:mini
   ```

### Verification
- [ ] `free -h` shows acceptable memory usage
- [ ] `docker stats` shows containers within limits
- [ ] Services stable for 5+ minutes

---

## Disk Recovery

### Symptoms
- "No space left on device" errors
- Containers fail to start
- Logs stop writing

### Procedure

1. **Check disk usage**
   ```bash
   # Overall disk usage
   df -h
   
   # Docker disk usage
   docker system df
   
   # Find large directories
   du -sh /* 2>/dev/null | sort -h | tail -20
   ```

2. **Clean Docker resources**
   ```bash
   # Remove unused containers, images, volumes
   docker system prune -af
   
   # Remove unused volumes (careful!)
   docker volume prune -f
   
   # Remove build cache
   docker builder prune -af
   ```

3. **Clean AI Beast data**
   ```bash
   # Remove old logs
   find ./logs -name "*.log" -mtime +7 -delete
   
   # Remove old backups
   find ./backups -mtime +30 -delete
   
   # Clear temp files
   rm -rf ./tmp/* ./.cache/*
   ```

4. **Remove unused models**
   ```bash
   # List models with sizes
   beast model list
   
   # Remove unused models
   beast model rm model_name
   ```

### Verification
- [ ] `df -h` shows >20% free space
- [ ] Services start without disk errors
- [ ] Logs writing correctly

---

## Rollback Procedures

### Restore from Backup

```bash
# List available backups
ls -la ./backups/

# Restore
./scripts/restore.sh ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz
```

### Revert Configuration Changes

```bash
# Reset to defaults
git checkout config/

# Or restore specific file
git checkout HEAD -- config/ai-beast.env
```

### Roll Back Docker Images

```bash
# List available versions
docker images | grep ai_beast

# Use specific version
docker compose up -d --pull never
```

---

## Related Runbooks

- [Backup and Restore](backup-restore.md)
- [Performance Tuning](performance-tuning.md)
- [Troubleshooting](troubleshooting.md)

## Change Log

| Date | Change | Author |
| ---- | ------ | ------ |
| 2025-01-09 | Initial creation | AI Beast Team |
