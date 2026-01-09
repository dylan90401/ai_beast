# AI Beast / Kryptos - Implementation Tasks (Part 2)
## Phases 6-10: Advanced Features, Extensions & Production Readiness

**Continuation from IMPLEMENTATION_TASKS.md**

---

## PHASE 6: ADDITIONAL EXTENSIONS & INTEGRATIONS (P2)

### Task 6.1: Implement N8N Workflow Automation Integration [P2, M]
**Directory:** `extensions/n8n/`

**compose.fragment.yaml:**
```yaml
# N8N Workflow Automation
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: ai_beast_n8n
    profiles: ["automation", "full", "prodish"]
    ports:
      - "${AI_BEAST_BIND_ADDR:-127.0.0.1}:${PORT_N8N:-5678}:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=false
      - N8N_HOST=${AI_BEAST_BIND_ADDR:-127.0.0.1}
      - N8N_PORT=${PORT_N8N:-5678}
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=http://${AI_BEAST_BIND_ADDR:-127.0.0.1}:${PORT_N8N:-5678}/
      - GENERIC_TIMEZONE=America/Los_Angeles
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY:-changeme}
    volumes:
      - n8n_data:/home/node/.n8n
      - ${DATA_DIR:-./data}/n8n/workflows:/workflows
    networks:
      - default
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:5678/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  n8n_data:
```

**Integration Module:**
```python
# modules/n8n/client.py
"""N8N workflow automation client."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)


class N8NClient:
    """N8N API client for workflow automation."""

    def __init__(self, context: AppContext):
        self.context = context
        self.base_url = f"http://127.0.0.1:{context.ports.get('PORT_N8N', 5678)}"
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def execute_workflow(
        self,
        workflow_id: str,
        data: dict[str, Any],
    ) -> dict:
        """Execute a workflow with data.

        Args:
            workflow_id: Workflow ID or name
            data: Input data for workflow

        Returns:
            Execution result
        """
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}/webhook/{workflow_id}"

        try:
            async with self._session.post(url, json=data) as resp:
                if resp.status != 200:
                    return {"ok": False, "error": f"HTTP {resp.status}"}
                return await resp.json()
        except Exception as e:
            logger.error("n8n_execute_failed", workflow=workflow_id, error=str(e))
            return {"ok": False, "error": str(e)}

    async def list_workflows(self) -> list[dict]:
        """List all workflows."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}/rest/workflows"

        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.error("n8n_list_failed", error=str(e))
            return []

    async def get_workflow(self, workflow_id: str) -> dict | None:
        """Get workflow details."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}/rest/workflows/{workflow_id}"

        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception as e:
            logger.error("n8n_get_workflow_failed", workflow=workflow_id, error=str(e))
            return None

    async def create_workflow(self, workflow: dict) -> dict:
        """Create a new workflow."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}/rest/workflows"

        try:
            async with self._session.post(url, json=workflow) as resp:
                if resp.status not in (200, 201):
                    return {"ok": False, "error": f"HTTP {resp.status}"}
                return await resp.json()
        except Exception as e:
            logger.error("n8n_create_workflow_failed", error=str(e))
            return {"ok": False, "error": str(e)}

    async def activate_workflow(self, workflow_id: str, active: bool = True) -> dict:
        """Activate or deactivate a workflow."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}/rest/workflows/{workflow_id}/activate"

        try:
            method = "post" if active else "delete"
            async with getattr(self._session, method)(url) as resp:
                if resp.status != 200:
                    return {"ok": False, "error": f"HTTP {resp.status}"}
                return {"ok": True}
        except Exception as e:
            logger.error("n8n_activate_failed", workflow=workflow_id, error=str(e))
            return {"ok": False, "error": str(e)}


# Pre-built workflows for common tasks
WORKFLOW_TEMPLATES = {
    "model_download_notify": {
        "name": "Model Download Notification",
        "nodes": [
            {
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "model-download",
                    "method": "POST",
                },
            },
            {
                "type": "n8n-nodes-base.slack",
                "parameters": {
                    "channel": "#ai-beast",
                    "text": "Model {{ $json.model_name }} downloaded ({{ $json.size_gb }} GB)",
                },
            },
        ],
    },
    "rag_ingest_pipeline": {
        "name": "RAG Document Ingestion",
        "nodes": [
            {
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "rag-ingest",
                    "method": "POST",
                },
            },
            {
                "type": "n8n-nodes-base.executeCommand",
                "parameters": {
                    "command": "./bin/beast rag ingest --dir={{ $json.directory }} --apply",
                },
            },
        ],
    },
}
```

**Related Files:**
- extensions/n8n/compose.fragment.yaml (update, ~40 lines)
- modules/n8n/client.py (new, ~200 lines)
- modules/n8n/__init__.py (new)
- tests/test_n8n_client.py (new, ~100 lines)
- workflows/n8n/templates/ (new directory with JSON workflows)

---

### Task 6.2: Add Jupyter Notebook Integration [P2, M]
**Directory:** `extensions/jupyter/`

**compose.fragment.yaml:**
```yaml
services:
  jupyter:
    image: jupyter/datascience-notebook:latest
    container_name: ai_beast_jupyter
    profiles: ["jupyter", "dev", "full"]
    ports:
      - "${AI_BEAST_BIND_ADDR:-127.0.0.1}:${PORT_JUPYTER:-8888}:8888"
    environment:
      - JUPYTER_ENABLE_LAB=yes
      - JUPYTER_TOKEN=${JUPYTER_TOKEN:-ai_beast}
    volumes:
      - ${DATA_DIR:-./data}/notebooks:/home/jovyan/work
      - ${MODELS_DIR:-./models}:/models:ro
      - ${BASE_DIR:-./}:/workspace:ro
    command: start-notebook.sh --NotebookApp.token='${JUPYTER_TOKEN:-ai_beast}'
    restart: unless-stopped

volumes:
  jupyter_data:
```

**Starter Notebooks:**
```python
# data/notebooks/01_Model_Management.ipynb
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# AI Beast - Model Management\n",
    "\n",
    "This notebook demonstrates model management operations."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "source": [
    "import sys\n",
    "sys.path.append('/workspace')\n",
    "\n",
    "from modules.container import AppContext\n",
    "from modules.llm.manager_async import AsyncLLMManager\n",
    "\n",
    "# Initialize\n",
    "context = AppContext.from_env()\n",
    "print(f\"Base Dir: {context.base_dir}\")\n",
    "print(f\"Models Dir: {context.models_dir}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "source": [
    "# List local models\n",
    "async with AsyncLLMManager(context) as manager:\n",
    "    models = await manager.scan_local_models_async(force=True)\n",
    "    \n",
    "    print(f\"Found {len(models)} models:\\n\")\n",
    "    for model in models:\n",
    "        print(f\"- {model.name}\")\n",
    "        print(f\"  Location: {model.location.value}\")\n",
    "        print(f\"  Size: {model.size_human}\")\n",
    "        print(f\"  Type: {model.model_type}\")\n",
    "        if model.quantization:\n",
    "            print(f\"  Quantization: {model.quantization}\")\n",
    "        print()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "source": [
    "# Check Ollama models\n",
    "async with AsyncLLMManager(context) as manager:\n",
    "    ollama_models = await manager.list_ollama_models_async()\n",
    "    \n",
    "    print(f\"Ollama models: {len(ollama_models)}\\n\")\n",
    "    for model in ollama_models:\n",
    "        print(f\"- {model.name} ({model.size_human})\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Storage Analysis"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "source": [
    "import pandas as pd\n",
    "import matplotlib.pyplot as plt\n",
    "\n",
    "# Analyze model storage\n",
    "async with AsyncLLMManager(context) as manager:\n",
    "    models = await manager.scan_local_models_async(force=True)\n",
    "    \n",
    "    # Create DataFrame\n",
    "    df = pd.DataFrame([m.to_dict() for m in models])\n",
    "    \n",
    "    # Storage by location\n",
    "    storage_by_location = df.groupby('location')['size_bytes'].sum() / (1024**3)\n",
    "    \n",
    "    plt.figure(figsize=(10, 6))\n",
    "    storage_by_location.plot(kind='bar')\n",
    "    plt.title('Model Storage by Location (GB)')\n",
    "    plt.ylabel('Size (GB)')\n",
    "    plt.xlabel('Location')\n",
    "    plt.xticks(rotation=45)\n",
    "    plt.tight_layout()\n",
    "    plt.show()\n",
    "    \n",
    "    print(f\"\\nTotal storage: {df['size_bytes'].sum() / (1024**3):.2f} GB\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
```

**Related Files:**
- extensions/jupyter/compose.fragment.yaml (new, ~25 lines)
- data/notebooks/01_Model_Management.ipynb (new, JSON notebook)
- data/notebooks/02_RAG_Analysis.ipynb (new)
- data/notebooks/03_Agent_Development.ipynb (new)
- data/notebooks/04_Performance_Profiling.ipynb (new)

---

### Task 6.3: Add Traefik Reverse Proxy [P2, M]
**Directory:** `extensions/traefik/`

**Purpose:** Unified access point with SSL/TLS termination

**compose.fragment.yaml:**
```yaml
services:
  traefik:
    image: traefik:v2.10
    container_name: ai_beast_traefik
    profiles: ["traefik", "prodish", "full"]
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Dashboard
    command:
      - "--api.dashboard=true"
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=admin@example.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_letsencrypt:/letsencrypt
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.localhost`)"
      - "traefik.http.routers.dashboard.service=api@internal"
    restart: unless-stopped

volumes:
  traefik_letsencrypt:
```

**Update other services with Traefik labels:**
```yaml
# extensions/open_webui/compose.fragment.yaml (add labels)
services:
  open-webui:
    # ... existing config ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.webui.rule=Host(`webui.localhost`)"
      - "traefik.http.routers.webui.entrypoints=web"
      - "traefik.http.services.webui.loadbalancer.server.port=8080"

# Similar labels for other services
```

**Traefik Configuration:**
```yaml
# config/traefik/dynamic.yml
http:
  routers:
    webui:
      rule: "Host(`ai-beast.local`)"
      service: webui
      entryPoints:
        - web
        - websecure
      tls:
        certResolver: myresolver

    dashboard:
      rule: "Host(`dashboard.ai-beast.local`)"
      service: dashboard
      entryPoints:
        - web
        - websecure

  services:
    webui:
      loadBalancer:
        servers:
          - url: "http://open-webui:8080"

    dashboard:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:8787"

  middlewares:
    auth:
      basicAuth:
        users:
          - "admin:$apr1$..."  # htpasswd generated

    ratelimit:
      rateLimit:
        average: 100
        burst: 50
```

**Related Files:**
- extensions/traefik/compose.fragment.yaml (new, ~40 lines)
- config/traefik/dynamic.yml (new, ~60 lines)
- config/traefik/traefik.yml (new, ~40 lines)
- scripts/setup_traefik.sh (new, ~50 lines)

---

### Task 6.4: Add Monitoring Stack (Prometheus + Grafana) [P2, L]
**Directory:** `extensions/monitoring/`

**compose.fragment.yaml:**
```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: ai_beast_prometheus
    profiles: ["monitoring", "prodish", "full"]
    ports:
      - "${AI_BEAST_BIND_ADDR:-127.0.0.1}:9090:9090"
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: ai_beast_grafana
    profiles: ["monitoring", "prodish", "full"]
    ports:
      - "${AI_BEAST_BIND_ADDR:-127.0.0.1}:3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./config/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:latest
    container_name: ai_beast_node_exporter
    profiles: ["monitoring", "prodish", "full"]
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--path.rootfs=/rootfs'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: ai_beast_cadvisor
    profiles: ["monitoring", "prodish", "full"]
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

**Prometheus Config:**
```yaml
# config/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'ai-beast-metrics'
    static_configs:
      - targets: ['host.docker.internal:9091']

  - job_name: 'ollama'
    static_configs:
      - targets: ['host.docker.internal:11434']
```

**Metrics Exporter:**
```python
# modules/monitoring/exporter.py
"""Prometheus metrics exporter for AI Beast."""

from prometheus_client import Counter, Gauge, Histogram, start_http_server
from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)

# Define metrics
MODEL_DOWNLOADS = Counter(
    'ai_beast_model_downloads_total',
    'Total number of model downloads',
    ['model_name', 'location']
)

MODEL_DOWNLOAD_SIZE = Histogram(
    'ai_beast_model_download_bytes',
    'Size of downloaded models in bytes',
    ['model_name']
)

MODEL_DOWNLOAD_DURATION = Histogram(
    'ai_beast_model_download_duration_seconds',
    'Duration of model downloads',
    ['model_name']
)

ACTIVE_MODELS = Gauge(
    'ai_beast_active_models',
    'Number of active models',
    ['location', 'type']
)

DISK_USAGE = Gauge(
    'ai_beast_disk_usage_bytes',
    'Disk usage in bytes',
    ['path', 'type']
)

OLLAMA_REQUESTS = Counter(
    'ai_beast_ollama_requests_total',
    'Total Ollama API requests',
    ['endpoint', 'status']
)

OLLAMA_REQUEST_DURATION = Histogram(
    'ai_beast_ollama_request_duration_seconds',
    'Ollama request duration',
    ['endpoint']
)

RAG_INGESTIONS = Counter(
    'ai_beast_rag_ingestions_total',
    'Total RAG document ingestions',
    ['collection', 'status']
)

RAG_CHUNKS = Counter(
    'ai_beast_rag_chunks_total',
    'Total RAG chunks created',
    ['collection']
)

AGENT_TASKS = Counter(
    'ai_beast_agent_tasks_total',
    'Total agent tasks executed',
    ['status']
)

AGENT_TASK_DURATION = Histogram(
    'ai_beast_agent_task_duration_seconds',
    'Agent task duration'
)


class MetricsExporter:
    """Metrics exporter server."""

    def __init__(self, context: AppContext, port: int = 9091):
        self.context = context
        self.port = port

    def start(self):
        """Start metrics server."""
        start_http_server(self.port)
        logger.info("metrics_server_started", port=self.port)

    async def update_metrics(self):
        """Update all metrics."""
        # Update model counts
        from modules.llm import LLMManager
        manager = LLMManager(self.context)
        models = manager.list_all_models(force_scan=True)

        # Clear gauges
        ACTIVE_MODELS._metrics.clear()

        # Count by location and type
        for model in models:
            ACTIVE_MODELS.labels(
                location=model.location.value,
                type=model.model_type
            ).inc()

        # Update disk usage
        storage = manager.get_storage_info()
        for name, info in storage.items():
            if 'used' in info:
                DISK_USAGE.labels(path=name, type='used').set(info['used'])
            if 'free' in info:
                DISK_USAGE.labels(path=name, type='free').set(info['free'])


# Decorators for automatic metrics
def track_ollama_request(endpoint: str):
    """Decorator to track Ollama requests."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with OLLAMA_REQUEST_DURATION.labels(endpoint=endpoint).time():
                try:
                    result = await func(*args, **kwargs)
                    OLLAMA_REQUESTS.labels(endpoint=endpoint, status='success').inc()
                    return result
                except Exception as e:
                    OLLAMA_REQUESTS.labels(endpoint=endpoint, status='error').inc()
                    raise
        return wrapper
    return decorator
```

**Grafana Dashboard:**
```json
{
  "dashboard": {
    "title": "AI Beast Overview",
    "panels": [
      {
        "title": "Model Downloads",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(ai_beast_model_downloads_total[5m])"
          }
        ]
      },
      {
        "title": "Active Models",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(ai_beast_active_models)"
          }
        ]
      },
      {
        "title": "Disk Usage",
        "type": "gauge",
        "targets": [
          {
            "expr": "ai_beast_disk_usage_bytes{type='used'} / ai_beast_disk_usage_bytes{type='total'} * 100"
          }
        ]
      },
      {
        "title": "Ollama Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(ai_beast_ollama_requests_total[5m])"
          }
        ]
      }
    ]
  }
}
```

**Related Files:**
- extensions/monitoring/compose.fragment.yaml (new, ~80 lines)
- config/prometheus/prometheus.yml (new, ~40 lines)
- config/grafana/dashboards/ai_beast.json (new, ~500 lines JSON)
- modules/monitoring/exporter.py (new, ~200 lines)
- requirements.txt (add prometheus-client>=0.18.0)

---

## PHASE 7: ADVANCED FEATURES (P2-P3)

### Task 7.1: Implement Model Registry & Catalog [P2, L]
**New Module:** `modules/registry/`

```python
# modules/registry/catalog.py
"""Model catalog and registry system."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)


class ModelFamily(str, Enum):
    """Model family/architecture."""
    LLAMA = "llama"
    MISTRAL = "mistral"
    GEMMA = "gemma"
    PHI = "phi"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    SDXL = "sdxl"
    FLUX = "flux"
    WHISPER = "whisper"
    OTHER = "other"


class ModelLicense(str, Enum):
    """Model license types."""
    MIT = "MIT"
    APACHE_2 = "Apache-2.0"
    GPL = "GPL"
    LLAMA = "Llama"
    CUSTOM = "Custom"
    UNKNOWN = "Unknown"


@dataclass
class ModelMetadata:
    """Complete model metadata."""

    # Identity
    id: str
    name: str
    version: str
    family: ModelFamily

    # Technical specs
    size_bytes: int
    parameter_count: int | None = None
    quantization: str | None = None
    context_length: int | None = None

    # Source
    source_url: str = ""
    source_repo: str = ""
    sha256: str = ""

    # Legal
    license: ModelLicense = ModelLicense.UNKNOWN
    license_url: str = ""

    # Capabilities
    tags: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    modalities: list[str] = field(default_factory=list)  # text, image, audio, video

    # Quality metrics
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    recommended_use: str = ""
    limitations: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str = ""
    description: str = ""

    # Usage
    download_count: int = 0
    rating: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["family"] = self.family.value
        data["license"] = self.license.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data


class ModelRegistry:
    """Centralized model registry with SQLite backend."""

    def __init__(self, context: AppContext):
        self.context = context
        self.db_path = context.data_dir / "registry" / "models.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    family TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    parameter_count INTEGER,
                    quantization TEXT,
                    context_length INTEGER,
                    source_url TEXT,
                    source_repo TEXT,
                    sha256 TEXT,
                    license TEXT,
                    license_url TEXT,
                    tags TEXT,
                    languages TEXT,
                    modalities TEXT,
                    benchmark_scores TEXT,
                    recommended_use TEXT,
                    limitations TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    author TEXT,
                    description TEXT,
                    download_count INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    UNIQUE(name, version)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_family ON models(family)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_name ON models(name)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_tags ON models(tags)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    location TEXT NOT NULL,
                    installed_at TEXT,
                    last_used TEXT,
                    use_count INTEGER DEFAULT 0,
                    FOREIGN KEY (model_id) REFERENCES models(id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_model ON model_instances(model_id)
            """)

            conn.commit()

    def register(self, metadata: ModelMetadata) -> bool:
        """Register a model in the catalog.

        Args:
            metadata: Model metadata

        Returns:
            True if registered successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO models (
                        id, name, version, family, size_bytes, parameter_count,
                        quantization, context_length, source_url, source_repo,
                        sha256, license, license_url, tags, languages, modalities,
                        benchmark_scores, recommended_use, limitations,
                        created_at, updated_at, author, description,
                        download_count, rating
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metadata.id,
                    metadata.name,
                    metadata.version,
                    metadata.family.value,
                    metadata.size_bytes,
                    metadata.parameter_count,
                    metadata.quantization,
                    metadata.context_length,
                    metadata.source_url,
                    metadata.source_repo,
                    metadata.sha256,
                    metadata.license.value,
                    metadata.license_url,
                    ",".join(metadata.tags),
                    ",".join(metadata.languages),
                    ",".join(metadata.modalities),
                    json.dumps(metadata.benchmark_scores),
                    metadata.recommended_use,
                    metadata.limitations,
                    metadata.created_at.isoformat(),
                    metadata.updated_at.isoformat(),
                    metadata.author,
                    metadata.description,
                    metadata.download_count,
                    metadata.rating,
                ))
                conn.commit()
                logger.info("model_registered", model_id=metadata.id, name=metadata.name)
                return True
            except sqlite3.Error as e:
                logger.error("model_register_failed", model_id=metadata.id, error=str(e))
                return False

    def get(self, model_id: str) -> ModelMetadata | None:
        """Get model by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_metadata(row)

    def search(
        self,
        query: str | None = None,
        family: ModelFamily | None = None,
        tags: list[str] | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        limit: int = 50,
    ) -> list[ModelMetadata]:
        """Search models by criteria.

        Args:
            query: Text search in name/description
            family: Model family filter
            tags: Required tags
            min_size: Minimum size in bytes
            max_size: Maximum size in bytes
            limit: Maximum results

        Returns:
            List of matching models
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            sql = "SELECT * FROM models WHERE 1=1"
            params: list[Any] = []

            if query:
                sql += " AND (name LIKE ? OR description LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])

            if family:
                sql += " AND family = ?"
                params.append(family.value)

            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f"%{tag}%")

            if min_size:
                sql += " AND size_bytes >= ?"
                params.append(min_size)

            if max_size:
                sql += " AND size_bytes <= ?"
                params.append(max_size)

            sql += " ORDER BY rating DESC, download_count DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            return [self._row_to_metadata(row) for row in cursor.fetchall()]

    def recommend(
        self,
        task: str,
        constraints: dict[str, Any] | None = None,
    ) -> list[ModelMetadata]:
        """Recommend models for a task.

        Args:
            task: Task description (e.g., "chat", "code", "image")
            constraints: Size/performance constraints

        Returns:
            Recommended models sorted by suitability
        """
        constraints = constraints or {}

        # Map task to tags
        task_tags = {
            "chat": ["chat", "instruct", "assistant"],
            "code": ["code", "programming"],
            "image": ["image", "vision", "multimodal"],
            "embedding": ["embedding", "retrieval"],
        }

        tags = task_tags.get(task.lower(), [task])

        # Apply constraints
        max_size = constraints.get("max_size_gb", 100) * 1024**3
        min_quality = constraints.get("min_rating", 0.0)

        models = self.search(tags=tags, max_size=max_size)

        # Filter by rating
        models = [m for m in models if m.rating >= min_quality]

        return models[:10]

    def register_instance(
        self,
        model_id: str,
        path: str,
        location: str,
    ) -> bool:
        """Register a model instance (installation).

        Args:
            model_id: Model ID
            path: File path
            location: Storage location

        Returns:
            True if registered successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO model_instances (
                        model_id, path, location, installed_at
                    ) VALUES (?, ?, ?, ?)
                """, (
                    model_id,
                    path,
                    location,
                    datetime.utcnow().isoformat(),
                ))
                conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error("instance_register_failed", error=str(e))
                return False

    def _row_to_metadata(self, row: sqlite3.Row) -> ModelMetadata:
        """Convert database row to ModelMetadata."""
        import json

        return ModelMetadata(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            family=ModelFamily(row["family"]),
            size_bytes=row["size_bytes"],
            parameter_count=row["parameter_count"],
            quantization=row["quantization"],
            context_length=row["context_length"],
            source_url=row["source_url"] or "",
            source_repo=row["source_repo"] or "",
            sha256=row["sha256"] or "",
            license=ModelLicense(row["license"]),
            license_url=row["license_url"] or "",
            tags=row["tags"].split(",") if row["tags"] else [],
            languages=row["languages"].split(",") if row["languages"] else [],
            modalities=row["modalities"].split(",") if row["modalities"] else [],
            benchmark_scores=json.loads(row["benchmark_scores"]) if row["benchmark_scores"] else {},
            recommended_use=row["recommended_use"] or "",
            limitations=row["limitations"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            author=row["author"] or "",
            description=row["description"] or "",
            download_count=row["download_count"],
            rating=row["rating"],
        )


# Pre-populate with known models
KNOWN_MODELS = [
    ModelMetadata(
        id="llama-3.2-3b-instruct",
        name="Llama 3.2 3B Instruct",
        version="3.2",
        family=ModelFamily.LLAMA,
        size_bytes=2_000_000_000,
        parameter_count=3_000_000_000,
        context_length=8192,
        source_url="https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
        source_repo="meta-llama/Llama-3.2-3B-Instruct",
        license=ModelLicense.LLAMA,
        tags=["chat", "instruct", "assistant"],
        languages=["en"],
        modalities=["text"],
        recommended_use="General purpose chat and assistance",
        author="Meta",
        description="Lightweight instruction-tuned model from Llama 3.2 series",
        rating=4.5,
    ),
    # Add more known models...
]
```

**CLI Integration:**
```python
# beast/cli.py - Add registry commands

def cmd_registry_list(filters: dict) -> None:
    """List models in registry."""
    from modules.registry import ModelRegistry
    from modules.container import AppContext

    context = AppContext.from_env()
    registry = ModelRegistry(context)

    models = registry.search(**filters)

    print(f"Found {len(models)} models:\n")
    for model in models:
        print(f"- {model.name} v{model.version}")
        print(f"  Family: {model.family.value}")
        print(f"  Size: {model.size_bytes / (1024**3):.2f} GB")
        print(f"  Rating: {model.rating:.1f}/5.0")
        if model.tags:
            print(f"  Tags: {', '.join(model.tags)}")
        print()


def cmd_registry_recommend(task: str, constraints: dict) -> None:
    """Recommend models for a task."""
    from modules.registry import ModelRegistry
    from modules.container import AppContext

    context = AppContext.from_env()
    registry = ModelRegistry(context)

    models = registry.recommend(task, constraints)

    print(f"Recommended models for '{task}':\n")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model.name} v{model.version}")
        print(f"   {model.description}")
        print(f"   Size: {model.size_bytes / (1024**3):.2f} GB | Rating: {model.rating:.1f}/5.0")
        print()
```

**Related Files:**
- modules/registry/catalog.py (new, ~500 lines)
- modules/registry/__init__.py (new)
- modules/registry/seed_data.py (new, ~500 lines with known models)
- beast/cli.py (add registry commands, ~100 lines)
- tests/test_registry.py (new, ~200 lines)

---

### Task 7.2: Implement Model Versioning & Rollback [P2, M]
**New Module:** `modules/versioning/`

```python
# modules/versioning/manager.py
"""Model versioning and rollback system."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ModelSnapshot:
    """Model version snapshot."""

    model_name: str
    version: str
    path: Path
    sha256: str
    size_bytes: int
    created_at: datetime
    metadata: dict


class VersionManager:
    """Manages model versions and rollback."""

    def __init__(self, context: AppContext):
        self.context = context
        self.snapshots_dir = context.data_dir / "versions"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, model_path: Path, metadata: dict | None = None) -> ModelSnapshot:
        """Create a versioned snapshot of a model.

        Args:
            model_path: Path to model file
            metadata: Optional metadata

        Returns:
            ModelSnapshot instance
        """
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Compute hash for version
        sha256 = self._compute_hash(model_path)
        version = sha256[:8]

        # Create snapshot directory
        snapshot_dir = self.snapshots_dir / model_path.stem
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = snapshot_dir / f"{model_path.stem}_{version}{model_path.suffix}"

        # Copy file if not already exists
        if not snapshot_path.exists():
            logger.info("creating_snapshot",
                       model=model_path.name,
                       version=version,
                       size_mb=model_path.stat().st_size / (1024**2))

            shutil.copy2(model_path, snapshot_path)

        snapshot = ModelSnapshot(
            model_name=model_path.stem,
            version=version,
            path=snapshot_path,
            sha256=sha256,
            size_bytes=snapshot_path.stat().st_size,
            created_at=datetime.fromtimestamp(snapshot_path.stat().st_mtime),
            metadata=metadata or {},
        )

        # Save metadata
        self._save_metadata(snapshot)

        logger.info("snapshot_created",
                   model=snapshot.model_name,
                   version=version,
                   path=str(snapshot_path))

        return snapshot

    def list_snapshots(self, model_name: str | None = None) -> list[ModelSnapshot]:
        """List all snapshots.

        Args:
            model_name: Optional filter by model name

        Returns:
            List of snapshots
        """
        snapshots = []

        if model_name:
            snapshot_dir = self.snapshots_dir / model_name
            if not snapshot_dir.exists():
                return []
            dirs = [snapshot_dir]
        else:
            dirs = [d for d in self.snapshots_dir.iterdir() if d.is_dir()]

        for snapshot_dir in dirs:
            for snapshot_file in snapshot_dir.glob("*"):
                if snapshot_file.is_file() and not snapshot_file.name.endswith(".json"):
                    metadata = self._load_metadata(snapshot_file)
                    if metadata:
                        snapshots.append(metadata)

        # Sort by creation time
        snapshots.sort(key=lambda s: s.created_at, reverse=True)

        return snapshots

    def get_snapshot(self, model_name: str, version: str) -> ModelSnapshot | None:
        """Get specific snapshot.

        Args:
            model_name: Model name
            version: Version ID

        Returns:
            ModelSnapshot or None
        """
        snapshots = self.list_snapshots(model_name)
        for snapshot in snapshots:
            if snapshot.version == version:
                return snapshot
        return None

    def rollback(self, model_name: str, target_version: str, destination: Path) -> bool:
        """Rollback model to a previous version.

        Args:
            model_name: Model name
            target_version: Target version to rollback to
            destination: Destination path for rollback

        Returns:
            True if successful
        """
        snapshot = self.get_snapshot(model_name, target_version)
        if not snapshot:
            logger.error("snapshot_not_found",
                        model=model_name,
                        version=target_version)
            return False

        try:
            # Create current snapshot before rollback
            if destination.exists():
                self.create_snapshot(destination, {"rollback_from": destination.stem})

            # Copy snapshot to destination
            logger.info("rolling_back",
                       model=model_name,
                       from_version="current",
                       to_version=target_version)

            shutil.copy2(snapshot.path, destination)

            logger.info("rollback_complete",
                       model=model_name,
                       version=target_version,
                       path=str(destination))

            return True

        except Exception as e:
            logger.error("rollback_failed",
                        model=model_name,
                        version=target_version,
                        error=str(e))
            return False

    def delete_snapshot(self, model_name: str, version: str) -> bool:
        """Delete a snapshot.

        Args:
            model_name: Model name
            version: Version to delete

        Returns:
            True if deleted
        """
        snapshot = self.get_snapshot(model_name, version)
        if not snapshot:
            return False

        try:
            snapshot.path.unlink()
            metadata_file = snapshot.path.with_suffix(".json")
            if metadata_file.exists():
                metadata_file.unlink()

            logger.info("snapshot_deleted",
                       model=model_name,
                       version=version)
            return True

        except Exception as e:
            logger.error("snapshot_delete_failed",
                        model=model_name,
                        version=version,
                        error=str(e))
            return False

    def cleanup_old_snapshots(self, model_name: str, keep_count: int = 5) -> int:
        """Clean up old snapshots, keeping only recent ones.

        Args:
            model_name: Model name
            keep_count: Number of snapshots to keep

        Returns:
            Number of snapshots deleted
        """
        snapshots = self.list_snapshots(model_name)

        if len(snapshots) <= keep_count:
            return 0

        # Delete oldest snapshots
        to_delete = snapshots[keep_count:]
        deleted = 0

        for snapshot in to_delete:
            if self.delete_snapshot(model_name, snapshot.version):
                deleted += 1

        logger.info("snapshots_cleaned",
                   model=model_name,
                   deleted=deleted,
                   kept=keep_count)

        return deleted

    def _compute_hash(self, path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _save_metadata(self, snapshot: ModelSnapshot):
        """Save snapshot metadata."""
        import json

        metadata_file = snapshot.path.with_suffix(".json")
        metadata = {
            "model_name": snapshot.model_name,
            "version": snapshot.version,
            "sha256": snapshot.sha256,
            "size_bytes": snapshot.size_bytes,
            "created_at": snapshot.created_at.isoformat(),
            "metadata": snapshot.metadata,
        }

        metadata_file.write_text(json.dumps(metadata, indent=2))

    def _load_metadata(self, snapshot_path: Path) -> ModelSnapshot | None:
        """Load snapshot metadata."""
        import json

        metadata_file = snapshot_path.with_suffix(".json")
        if not metadata_file.exists():
            return None

        try:
            data = json.loads(metadata_file.read_text())
            return ModelSnapshot(
                model_name=data["model_name"],
                version=data["version"],
                path=snapshot_path,
                sha256=data["sha256"],
                size_bytes=data["size_bytes"],
                created_at=datetime.fromisoformat(data["created_at"]),
                metadata=data.get("metadata", {}),
            )
        except Exception as e:
            logger.error("metadata_load_failed",
                        path=str(metadata_file),
                        error=str(e))
            return None


# CLI integration
def cmd_version_list(model_name: str | None) -> None:
    """List model versions."""
    from modules.versioning import VersionManager
    from modules.container import AppContext

    context = AppContext.from_env()
    manager = VersionManager(context)

    snapshots = manager.list_snapshots(model_name)

    if not snapshots:
        print("No snapshots found")
        return

    print(f"Model Snapshots ({len(snapshots)}):\n")
    for snapshot in snapshots:
        print(f"- {snapshot.model_name} v{snapshot.version}")
        print(f"  Created: {snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Size: {snapshot.size_bytes / (1024**2):.2f} MB")
        print(f"  Hash: {snapshot.sha256[:16]}...")
        print()


def cmd_version_rollback(model_name: str, version: str, path: str) -> None:
    """Rollback to a version."""
    from modules.versioning import VersionManager
    from modules.container import AppContext

    context = AppContext.from_env()
    manager = VersionManager(context)

    destination = Path(path)
    success = manager.rollback(model_name, version, destination)

    if success:
        print(f"✓ Rolled back {model_name} to version {version}")
    else:
        print(f"✗ Rollback failed")
        raise SystemExit(1)
```

**Related Files:**
- modules/versioning/manager.py (new, ~350 lines)
- modules/versioning/__init__.py (new)
- beast/cli.py (add version commands, ~80 lines)
- tests/test_versioning.py (new, ~150 lines)

---

### Task 7.3: Add Distributed Task Queue [P3, L]
**Purpose:** Handle long-running operations asynchronously

**New Module:** `modules/queue/`

```python
# modules/queue/worker.py
"""Background task queue using Redis and RQ."""

from __future__ import annotations

import time
from typing import Any, Callable

from redis import Redis
from rq import Queue, Worker
from rq.job import Job

from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)


class TaskQueue:
    """Task queue manager."""

    def __init__(self, context: AppContext):
        self.context = context
        self.redis_host = context.ports.get("REDIS_HOST", "localhost")
        self.redis_port = context.ports.get("REDIS_PORT", 6379)
        self.redis = Redis(host=self.redis_host, port=self.redis_port)
        self.queue = Queue(connection=self.redis, name="ai_beast_tasks")

    def enqueue(
        self,
        func: Callable,
        *args,
        timeout: int = 3600,
        result_ttl: int = 86400,
        **kwargs
    ) -> Job:
        """Enqueue a task.

        Args:
            func: Function to execute
            *args: Function arguments
            timeout: Job timeout in seconds
            result_ttl: Result TTL in seconds
            **kwargs: Function keyword arguments

        Returns:
            Job instance
        """
        job = self.queue.enqueue(
            func,
            *args,
            timeout=timeout,
            result_ttl=result_ttl,
            **kwargs
        )

        logger.info("task_enqueued",
                   job_id=job.id,
                   func=func.__name__)

        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        return Job.fetch(job_id, connection=self.redis)

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get job status.

        Returns:
            Dict with status, result, error keys
        """
        try:
            job = self.get_job(job_id)
            if not job:
                return {"status": "not_found"}

            status = job.get_status()

            result = {
                "status": status,
                "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            }

            if status == "finished":
                result["result"] = job.result
            elif status == "failed":
                result["error"] = str(job.exc_info)

            return result

        except Exception as e:
            logger.error("get_job_status_failed", job_id=job_id, error=str(e))
            return {"status": "error", "error": str(e)}

    def start_worker(self, burst: bool = False):
        """Start a worker.

        Args:
            burst: Run worker in burst mode (exit after jobs complete)
        """
        worker = Worker([self.queue], connection=self.redis)

        logger.info("worker_starting", burst=burst)

        worker.work(burst=burst)


# Task functions (these run in worker processes)
def download_model_task(url: str, destination: str, context_dict: dict) -> dict:
    """Background task: Download model."""
    from modules.container import AppContext
    from modules.llm.manager_async import AsyncLLMManager
    import asyncio

    logger.info("download_task_started", url=url)

    # Reconstruct context
    context = AppContext(**context_dict)

    async def download():
        async with AsyncLLMManager(context) as manager:
            return await manager.download_from_url_async(url)

    result = asyncio.run(download())

    logger.info("download_task_completed", url=url, ok=result.get("ok"))

    return result


def rag_ingest_task(directory: str, collection: str, context_dict: dict) -> dict:
    """Background task: RAG ingestion."""
    from modules.container import AppContext
    from modules.rag.ingest import ingest_directory

    logger.info("rag_ingest_task_started", directory=directory)

    context = AppContext(**context_dict)

    result = ingest_directory(
        directory=directory,
        collection=collection,
        apply=True
    )

    logger.info("rag_ingest_task_completed",
               directory=directory,
               files=result.get("files", 0),
               chunks=result.get("chunks", 0))

    return result


def agent_task(task: str, context_dict: dict) -> dict:
    """Background task: Agent execution."""
    from modules.container import AppContext
    from modules.agent import AgentOrchestrator

    logger.info("agent_task_started", task=task)

    context = AppContext(**context_dict)
    orchestrator = AgentOrchestrator(base_dir=context.base_dir, apply=True)

    state = orchestrator.run_task(task)

    result = {
        "status": state.status,
        "result": state.result,
        "error": state.error,
        "files_touched": state.files_touched,
        "tools_used": state.tools_used,
    }

    logger.info("agent_task_completed", status=state.status)

    return result
```

**Dashboard Integration:**
```python
# apps/dashboard/dashboard.py - Add queue endpoints

@app.route("/api/queue/jobs")
async def api_queue_jobs():
    """List queued jobs."""
    if not _auth():
        return _json(401, {"ok": False, "error": "Unauthorized"})

    from modules.queue import TaskQueue

    queue = TaskQueue(context)
    jobs = []

    for job in queue.queue.jobs:
        jobs.append({
            "id": job.id,
            "func": job.func_name,
            "status": job.get_status(),
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
        })

    return _json(200, {"ok": True, "jobs": jobs})


@app.route("/api/queue/status/<job_id>")
async def api_queue_status(job_id: str):
    """Get job status."""
    if not _auth():
        return _json(401, {"ok": False, "error": "Unauthorized"})

    from modules.queue import TaskQueue

    queue = TaskQueue(context)
    status = queue.get_job_status(job_id)

    return _json(200, {"ok": True, **status})


@app.route("/api/models/download", methods=["POST"])
async def api_model_download():
    """Download model (async via queue)."""
    if not _auth():
        return _json(401, {"ok": False, "error": "Unauthorized"})

    from modules.queue import TaskQueue, download_model_task

    data = await request.get_json()
    url = data.get("url")

    if not url:
        return _json(400, {"ok": False, "error": "Missing URL"})

    queue = TaskQueue(context)

    # Enqueue download task
    job = queue.enqueue(
        download_model_task,
        url,
        data.get("destination", "internal"),
        context.to_dict()  # Serialize context
    )

    return _json(200, {
        "ok": True,
        "job_id": job.id,
        "message": "Download queued"
    })
```

**Worker Service:**
```bash
#!/usr/bin/env bash
# bin/worker
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load environment
# shellcheck disable=SC1091
source "$BASE_DIR/config/ai-beast.env" 2>/dev/null || true

# Start worker
python3 -m modules.queue.worker "$@"
```

**Docker Service:**
```yaml
# docker/compose.ops.yaml - Add worker service
services:
  worker:
    image: python:3.12-slim
    container_name: ai_beast_worker
    profiles: ["worker", "prodish", "full"]
    depends_on:
      - redis
    environment:
      - BASE_DIR=/workspace
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    volumes:
      - ${BASE_DIR:-./}:/workspace
      - ${MODELS_DIR:-./models}:/models
    working_dir: /workspace
    command: python3 -m modules.queue.worker --burst=false
    restart: unless-stopped
```

**Related Files:**
- modules/queue/worker.py (new, ~250 lines)
- modules/queue/__init__.py (new)
- bin/worker (new shell script, ~20 lines)
- docker/compose.ops.yaml (add worker service, ~20 lines)
- requirements.txt (add redis>=5.0.0, rq>=1.15.0)
- tests/test_queue.py (new, ~150 lines)

---

### Task 7.4: Add Event-Driven Architecture [P3, L]
**Purpose:** Decouple components via event bus

**New Module:** `modules/events/`

```python
# modules/events/bus.py
"""Event-driven architecture with async event bus."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine

from modules.logging_config import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Event types."""

    # Model events
    MODEL_DOWNLOADED = "model.downloaded"
    MODEL_DELETED = "model.deleted"
    MODEL_UPDATED = "model.updated"

    # RAG events
    RAG_INGESTED = "rag.ingested"
    RAG_QUERIED = "rag.queried"

    # Agent events
    AGENT_TASK_STARTED = "agent.task.started"
    AGENT_TASK_COMPLETED = "agent.task.completed"
    AGENT_TASK_FAILED = "agent.task.failed"

    # Service events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    SERVICE_ERROR = "service.error"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


@dataclass
class Event:
    """Event with metadata."""

    type: EventType
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "unknown"
    id: str = field(default_factory=lambda: str(id(object())))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "id": self.id,
        }


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus for pub/sub messaging."""

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._event_history: list[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Event type to subscribe to
            handler: Async handler function
        """
        self._handlers[event_type].append(handler)
        logger.info("event_subscribed",
                   event_type=event_type.value,
                   handler=handler.__name__)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.info("event_unsubscribed",
                       event_type=event_type.value,
                       handler=handler.__name__)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        logger.info("event_published",
                   event_type=event.type.value,
                   source=event.source)

        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Call all handlers
        handlers = self._handlers.get(event.type, [])

        if not handlers:
            logger.debug("event_no_handlers", event_type=event.type.value)
            return

        # Execute handlers concurrently
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any handler errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("event_handler_error",
                           event_type=event.type.value,
                           handler=handlers[i].__name__,
                           error=str(result))

    def get_history(
        self,
        event_type: EventType | None = None,
        limit: int = 100
    ) -> list[Event]:
        """Get event history.

        Args:
            event_type: Optional filter by event type
            limit: Maximum events to return

        Returns:
            List of events
        """
        events = self._event_history

        if event_type:
            events = [e for e in events if e.type == event_type]

        return events[-limit:]


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Example handlers
async def on_model_downloaded(event: Event) -> None:
    """Handle model downloaded event."""
    logger.info("handling_model_downloaded",
               model_name=event.payload.get("model_name"),
               size_gb=event.payload.get("size_gb"))

    # Could trigger:
    # - Notification
    # - Model scanning
    # - Registry update
    # - etc.


async def on_rag_ingested(event: Event) -> None:
    """Handle RAG ingestion event."""
    logger.info("handling_rag_ingested",
               collection=event.payload.get("collection"),
               chunks=event.payload.get("chunks"))

    # Could trigger:
    # - Index optimization
    # - Notification
    # - etc.


# Setup default handlers
def setup_default_handlers():
    """Setup default event handlers."""
    bus = get_event_bus()

    bus.subscribe(EventType.MODEL_DOWNLOADED, on_model_downloaded)
    bus.subscribe(EventType.RAG_INGESTED, on_rag_ingested)

    logger.info("default_handlers_registered")
```

**Integration with LLM Manager:**
```python
# modules/llm/manager_async.py - Add event publishing

async def download_from_url_async(self, ...) -> dict:
    """Download with event publishing."""
    from modules.events import get_event_bus, Event, EventType

    # ... download logic ...

    # Publish event on success
    if result["ok"]:
        event = Event(
            type=EventType.MODEL_DOWNLOADED,
            payload={
                "model_name": filename,
                "url": url,
                "path": str(dest_path),
                "size_bytes": downloaded,
                "size_gb": downloaded / (1024**3),
            },
            source="llm_manager"
        )

        bus = get_event_bus()
        await bus.publish(event)

    return result
```

**Related Files:**
- modules/events/bus.py (new, ~250 lines)
- modules/events/__init__.py (new)
- modules/llm/manager_async.py (update to publish events)
- modules/rag/ingest.py (update to publish events)
- modules/agent/__init__.py (update to publish events)
- tests/test_events.py (new, ~150 lines)

---

Due to length, I'll create a summary of remaining tasks:

**Related Files:**
- IMPLEMENTATION_TASKS_PART2.md (this file)
- IMPLEMENTATION_TASKS_PART3.md (continuation needed for Phases 8-10)

## Remaining Phases Preview:

**Phase 8: Performance & Optimization**
- Task 8.1: Add File System Watcher for Cache Invalidation
- Task 8.2: Implement Connection Pooling for Databases
- Task 8.3: Add Request Caching Layer
- Task 8.4: Optimize Docker Images
- Task 8.5: Add Parallel Processing for RAG

**Phase 9: Documentation & Polish**
- Task 9.1: Generate API Documentation with Sphinx
- Task 9.2: Create Architecture Diagrams (C4 Model)
- Task 9.3: Write Operational Runbooks
- Task 9.4: Add Interactive Tutorials
- Task 9.5: Create Video Documentation

**Phase 10: Production Readiness**
- Task 10.1: Add Health Check Endpoints
- Task 10.2: Implement Circuit Breakers
- Task 10.3: Add Rate Limiting
- Task 10.4: Setup Backup & Recovery Automation
- Task 10.5: Production Security Hardening
- Task 10.6: Load Testing & Benchmarking
- Task 10.7: CI/CD Pipeline Enhancement
- Task 10.8: Release Automation

Total estimated tasks: 80+ detailed tasks across all phases.

Would you like me to continue with Part 3 (Phases 8-10)?
