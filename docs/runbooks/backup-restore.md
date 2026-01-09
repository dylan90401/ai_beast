# Backup and Restore Runbook

## Overview

This runbook covers backup and restore procedures for AI Beast data, configurations, and models.

**Severity**: P1 (High)  
**Time to Complete**: 5-60 minutes depending on data size  
**Last Updated**: 2025-01-09

## Prerequisites

- Write access to backup storage location
- Sufficient disk space for backups
- No active write operations during backup (recommended)

## What Gets Backed Up

| Component | Location | Backup Type | Priority |
| --------- | -------- | ----------- | -------- |
| Configuration | `config/` | Config | Critical |
| Vector Data | `data/` | Full | High |
| Models | `models/` | Full | Medium |
| Documents | `data/documents/` | Full | High |
| Docker Volumes | Docker | Volume | High |

---

## Backup Procedures

### Quick Backup (Config Only)

**Use when**: You only need to save configuration changes.

```bash
# Config-only backup (fast)
./scripts/backup.sh -t config

# Output: ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz
```

### Full Backup

**Use when**: Regular scheduled backups, before major changes.

```bash
# Full backup with compression
./scripts/backup.sh

# Or explicitly
./scripts/backup.sh -t full -c

# With encryption
./scripts/backup.sh -e

# Output: ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz
```

### Incremental Backup

**Use when**: Daily backups to save space.

```bash
# Incremental (only changes since last backup)
./scripts/backup.sh -t incremental

# Requires a previous full backup to exist
```

### Manual Backup (Component-Specific)

**Use when**: You need to backup specific components.

#### Configuration Only
```bash
tar -czvf config_backup.tar.gz config/
```

#### Qdrant Data Only
```bash
# Stop Qdrant first for consistency
docker compose stop qdrant

# Backup volume
docker run --rm \
  -v ai_beast_qdrant_data:/source:ro \
  -v $(pwd)/backups:/backup \
  alpine tar -czvf /backup/qdrant_data.tar.gz -C /source .

# Restart Qdrant
docker compose start qdrant
```

#### PostgreSQL Database
```bash
# Dump PostgreSQL
docker exec ai_beast_postgres \
  pg_dumpall -U postgres > backups/postgres_dump.sql

# Compress
gzip backups/postgres_dump.sql
```

---

## Restore Procedures

### Full Restore

**Use when**: Complete system recovery, migration to new host.

```bash
# Full restore from backup
./scripts/restore.sh ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz

# This will:
# 1. Create a pre-restore backup
# 2. Stop all services
# 3. Restore all data
# 4. Restart services
```

### Selective Restore

**Use when**: You only need to restore specific components.

```bash
# Restore only config
./scripts/restore.sh -c config ./backups/backup.tar.gz

# Restore only data
./scripts/restore.sh -c data ./backups/backup.tar.gz

# Restore multiple components
./scripts/restore.sh -c data,databases ./backups/backup.tar.gz
```

### Dry Run (Preview)

**Use when**: You want to see what would be restored.

```bash
# Preview restore without making changes
./scripts/restore.sh -n ./backups/backup.tar.gz
```

### Manual Restore (Component-Specific)

#### Configuration
```bash
# Stop services
make down

# Extract config
tar -xzvf config_backup.tar.gz -C ./

# Restart
make up
```

#### Qdrant Data
```bash
# Stop Qdrant
docker compose stop qdrant

# Clear existing data
docker volume rm ai_beast_qdrant_data
docker volume create ai_beast_qdrant_data

# Restore data
docker run --rm \
  -v ai_beast_qdrant_data:/dest \
  -v $(pwd)/backups:/backup:ro \
  alpine tar -xzvf /backup/qdrant_data.tar.gz -C /dest

# Start Qdrant
docker compose start qdrant
```

#### PostgreSQL Database
```bash
# Decompress
gunzip backups/postgres_dump.sql.gz

# Restore
cat backups/postgres_dump.sql | docker exec -i ai_beast_postgres \
  psql -U postgres
```

---

## Backup Schedule Recommendations

### Production Environment

| Backup Type | Frequency | Retention |
| ----------- | --------- | --------- |
| Full | Weekly (Sunday) | 4 weeks |
| Incremental | Daily | 7 days |
| Config | After changes | 10 versions |

### Development Environment

| Backup Type | Frequency | Retention |
| ----------- | --------- | --------- |
| Full | Before major changes | 2 weeks |
| Config | After changes | 5 versions |

### Automated Backup (Cron)

```bash
# Edit crontab
crontab -e

# Add backup schedule
# Full backup every Sunday at 2 AM
0 2 * * 0 /path/to/ai_beast/scripts/backup.sh -t full

# Incremental backup daily at 3 AM
0 3 * * 1-6 /path/to/ai_beast/scripts/backup.sh -t incremental

# Cleanup old backups weekly
0 4 * * 0 find /path/to/ai_beast/backups -mtime +30 -delete
```

---

## Verification

### After Backup

```bash
# Check backup file exists and has content
ls -lh ./backups/ai_beast_backup_*.tar.gz

# Verify archive integrity
tar -tzf ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz | head

# Check checksum
cat ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz.sha256
sha256sum ./backups/ai_beast_backup_YYYYMMDD_HHMMSS.tar.gz
```

### After Restore

```bash
# Check all services running
beast status

# Health check
beast health

# Verify data
beast model list              # Models restored
beast rag collections         # Collections restored
curl http://localhost:6333/collections  # Qdrant data

# Test functionality
beast generate llama3.2 "Hello world"
beast rag query "test query"
```

---

## Troubleshooting

### Backup Fails

**Symptom**: Backup script exits with error

**Solutions**:
```bash
# Check disk space
df -h

# Check permissions
ls -la ./backups/

# Run with verbose output
./scripts/backup.sh -v -t full

# Check Docker is running
docker info
```

### Restore Fails

**Symptom**: Restore script fails or services don't start

**Solutions**:
```bash
# Check backup file integrity
tar -tzf backup.tar.gz

# Check disk space
df -h

# Manual extraction
mkdir -p /tmp/restore_test
tar -xzf backup.tar.gz -C /tmp/restore_test

# Check for corruption
ls -la /tmp/restore_test/
```

### Data Inconsistency After Restore

**Symptom**: Services start but data is missing or corrupted

**Solutions**:
```bash
# Re-index Qdrant
beast rag reindex

# Verify model integrity
beast model verify llama3.2

# Check for newer backup
ls -lt ./backups/
```

---

## Off-Site Backup

### To Cloud Storage (S3-compatible)

```bash
# Install MinIO client
brew install minio-mc

# Configure
mc alias set backup https://s3.example.com ACCESS_KEY SECRET_KEY

# Upload backup
mc cp ./backups/ai_beast_backup_*.tar.gz backup/ai_beast/

# Download backup
mc cp backup/ai_beast/ai_beast_backup_YYYYMMDD.tar.gz ./backups/
```

### To Remote Server

```bash
# Rsync to remote
rsync -avz ./backups/ user@backup-server:/backups/ai_beast/

# With SSH key
rsync -avz -e "ssh -i ~/.ssh/backup_key" ./backups/ user@backup-server:/backups/ai_beast/
```

---

## Related Runbooks

- [Service Recovery](service-recovery.md)
- [Disaster Recovery](disaster-recovery.md)
- [Migration Guide](migration.md)

## Change Log

| Date | Change | Author |
| ---- | ------ | ------ |
| 2025-01-09 | Initial creation | AI Beast Team |
