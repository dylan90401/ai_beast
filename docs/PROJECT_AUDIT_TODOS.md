# AI Beast Project Audit - Comprehensive TODO List

**Date:** 2026-01-10
**Audit Scope:** UI Components, LLM Integration, Modal Dialogs, Settings, Resume Parsing

---

## 🎯 Executive Summary

This document contains a comprehensive audit of the AI Beast project, covering:
- **73 specific audit items** across all major components
- **UI elements:** 20 button actions, 3 modal dialogs, multiple form inputs
- **LLM integration:** 7 API endpoints, 6 core manager methods, Ollama streaming
- **Settings:** 30 feature flags, 12 packs, path configurations
- **⚠️ CRITICAL FINDING:** No resume parsing functionality exists (potential feature gap)

---

## 📊 Dashboard UI Components & Button Actions

### Authentication & Core Controls
1. **Token Input Field** (line 227, index.html)
   - Purpose: Store dashboard authentication token
   - Location: Top control bar
   - Storage: localStorage as `beast_token`

2. **Save Token Button** (line 229)
   - Function: `saveToken()`
   - Action: Saves token to localStorage, triggers `refreshAll()`

3. **Refresh Button** (line 230)
   - Function: `refreshAll()`
   - Action: Reloads config, packs, extensions, metrics, models, services

4. **Health Status Pill** (line 232)
   - Function: `setHealth()`
   - States: online (green) / offline (red)
   - Updates: On initial load and refresh

### System Action Buttons (lines 244-251)
All buttons call `runCmd(commandKey)` which triggers `/api/run?cmd=<key>`

5. **Preflight Button**
   - Command: `bin/beast preflight`
   - Purpose: Pre-flight system checks

6. **Status Button**
   - Command: `bin/beast status`
   - Purpose: Show stack status

7. **Doctor Button**
   - Command: `bin/beast doctor`
   - Purpose: System diagnostics

8. **Compose Gen Button**
   - Command: `bin/beast compose gen --apply`
   - Purpose: Regenerate docker-compose configuration

9. **Up Button**
   - Command: `bin/beast up`
   - Purpose: Start services

10. **Down Button**
    - Command: `bin/beast down`
    - Purpose: Stop services

11. **Speech Up Button**
    - Command: `bin/beast speech up`
    - Purpose: Start speech services

12. **Speech Down Button**
    - Command: `bin/beast speech down`
    - Purpose: Stop speech services

### Storage Path Configuration (lines 261-262)
13. **GUTS_DIR Input Field**
    - Purpose: Internal storage path (apps, venv)
    - Pre-populated from: `state.config.GUTS_DIR`

14. **HEAVY_DIR Input Field**
    - Purpose: External storage path (models, data)
    - Pre-populated from: `state.config.HEAVY_DIR`

15. **Save Paths Button** (line 265)
    - Function: `savePaths()`
    - API: POST `/api/paths`
    - Action: Runs `bin/beast init --apply` with new paths

### LLM Model Management (lines 273-306)
16. **Scan Models Button** (line 273)
    - Function: `refreshModels()`
    - API: GET `/api/models?force=1`
    - Action: Force re-scan local + Ollama models

17. **Ollama Library Button** (line 274)
    - Function: `showOllamaLibrary()`
    - Action: Toggle library panel, load available models

18. **Download from URL Button** (line 275)
    - Function: `showUrlDownload()`
    - Action: Toggle URL download panel

19. **Model Delete Buttons** (lines 991)
    - Function: `deleteModel(path)`
    - API: POST `/api/models/delete`
    - Confirmation: Modal confirm dialog
    - Action: Delete local or Ollama model

### Toggle Switches
20. **Pack Toggles** (lines 712-746)
    - Function: `togglePack(name, enable)`
    - API: POST `/api/toggle` with `kind: 'pack'`
    - Action: Enable/disable entire pack

21. **Extension Toggles** (lines 755-777)
    - Function: `toggleExtension(name, enable)`
    - API: POST `/api/toggle` with `kind: 'extension'`
    - Action: Enable/disable extension

22. **Capability Toggles** (lines 625-649)
    - Function: `toggleCapability(id, enable)`
    - Action: Auto-enable required packs + extensions
    - Smart: Only disables if no other capability needs it

23. **Extension Install Buttons** (line 765)
    - Function: `installExtension(name)`
    - API: POST `/api/extensions/install`
    - Condition: Only shown if `has_installer === 'true'`

### Output Display
24. **Terminal/Command Output** (line 333)
    - Element: `#log` with class `.terminal`
    - Updates: All command outputs, error messages
    - Style: Monospace, scrollable, max-height 260px

---

## 🪟 Modal Dialogs

### 1. URL Download Panel (lines 279-290)
**Trigger:** Click "Download from URL" button
**Toggle Logic:** `showUrlDownload()` - hides Ollama Library when shown

**Components:**
- **Model URL Input** (line 282)
  - Placeholder: "https://huggingface.co/.../model.gguf"
  - Accepts: Any URL (Hugging Face, direct links, etc.)

- **Destination Selector** (lines 283-287)
  - Options: Internal, External, Custom
  - Default: Internal
  - OnChange: Shows/hides custom path input

- **Custom Path Input** (line 290)
  - Visibility: Conditional (only if destination === 'custom')
  - Placeholder: "Custom path (if selected)"

- **Download Button** (line 288)
  - Function: `downloadFromUrl()`
  - Validation: Checks URL presence, custom path if needed
  - Action: POST `/api/models/download`

### 2. Ollama Library Panel (lines 292-295)
**Trigger:** Click "Ollama Library" button
**Toggle Logic:** `showOllamaLibrary()` - hides URL Download when shown

**Components:**
- **Model List Container** (line 294)
  - Element: `#ollamaLibraryList`
  - Layout: Flex wrap with gap
  - Max-height: 300px, scrollable

- **Model Buttons** (generated dynamically, line 1027)
  - Data source: `/api/models/available`
  - Count: 20 popular models (hardcoded in manager.py)
  - OnClick: `pullOllamaModel(name)`
  - Tooltip: Shows description and size

**Available Models:**
- llama3.2:3b, llama3.2:1b, llama3.1:8b, llama3.1:70b
- mistral:7b, mixtral:8x7b
- codellama:7b, codellama:34b
- deepseek-coder:6.7b, deepseek-coder-v2:16b
- phi3:mini, phi3:medium
- gemma2:9b, gemma2:27b
- qwen2.5:7b, qwen2.5:72b
- command-r:35b
- nomic-embed-text, mxbai-embed-large, all-minilm

### 3. Download Progress Panel (lines 296-305)
**Trigger:** Auto-shown during model pull/download
**Hidden:** On completion or error

**Components:**
- **Progress Text** (line 298)
  - Element: `#downloadName`
  - Content: "Downloading: {model_name}"

- **Progress Percentage** (line 300)
  - Element: `#downloadPercent`
  - Format: "XX%"

- **Progress Bar** (line 303)
  - Element: `#downloadBar`
  - Width: Animates 0-100%
  - Color: var(--accent) (yellow)
  - Update frequency: 1-second polling via `pollDownloadStatus()`

---

## 🤖 LLM Events & Data Flow

### Backend API Endpoints (dashboard.py)

#### GET /api/models (lines 443-456)
**Purpose:** List all models (local + Ollama)
**Auth:** Required (X-Beast-Token)
**Query params:**
- `force`: "1" or "true" to force re-scan

**Response:**
```json
{
  "ok": true,
  "models": [...ModelInfo],
  "ollama_running": true/false
}
```

**Data flow:**
1. Get LLMManager instance
2. Call `list_all_models(force_scan=force)`
3. Check Ollama status via `ollama_running()`
4. Return model list + Ollama status

#### GET /api/models/available (lines 457-467)
**Purpose:** List popular Ollama models from library
**Auth:** Required
**Response:**
```json
{
  "ok": true,
  "models": [
    {"name": "llama3.2:3b", "desc": "Meta Llama 3.2 3B", "size": "2.0GB"},
    ...
  ]
}
```

**Data source:** Hardcoded list in `manager.py:286-310`

#### GET /api/models/storage (lines 468-478)
**Purpose:** Get storage info for model directories
**Auth:** Required
**Response:**
```json
{
  "ok": true,
  "storage": {
    "internal": {
      "path": "/path/to/models/llm",
      "total": bytes,
      "used": bytes,
      "free": bytes,
      "free_human": "123.4 GB",
      "percent_used": 45.2
    },
    "external": {...},
    "models_root": {...}
  }
}
```

#### GET /api/models/downloads (lines 479-491)
**Purpose:** Get status of active downloads
**Auth:** Required
**Query params:**
- `id`: Optional download ID (returns specific download)

**Response:**
```json
{
  "ok": true,
  "downloads": {
    "status": "downloading|complete|error",
    "progress": 45.2,
    "downloaded": bytes,
    "total": bytes,
    "error": "error message if failed"
  }
}
```

#### POST /api/models/pull (lines 556-572)
**Purpose:** Pull model from Ollama registry
**Auth:** Required
**Body:**
```json
{
  "model": "llama3.2:3b"
}
```

**Data flow:**
1. Validate model name
2. Call `mgr.pull_ollama_model(model_name)`
3. Stream NDJSON responses from Ollama API
4. Return success/failure

**Ollama API:** Streams progress via `/api/pull` endpoint

#### POST /api/models/delete (lines 573-591)
**Purpose:** Delete a model (local or Ollama)
**Auth:** Required
**Body:**
```json
{
  "path": "/full/path/to/model.gguf" | "ollama:model_name"
}
```

**Logic:**
- If path starts with "ollama:": Call `delete_ollama_model()`
- Otherwise: Call `delete_local_model()`

**Safety:** Only deletes from allowed model directories

#### POST /api/models/download (lines 592-618)
**Purpose:** Download model from URL
**Auth:** Required
**Body:**
```json
{
  "url": "https://...",
  "filename": "optional",
  "destination": "internal|external|custom",
  "custom_path": "/optional/custom/path"
}
```

**Data flow:**
1. Validate URL and destination
2. Call `mgr.download_from_url()`
3. Start background thread with progress tracking
4. Return download ID for polling

**Progress tracking:** Via `_downloads` dict in LLMManager

#### POST /api/models/move (lines 619-644)
**Purpose:** Move model to different location
**Auth:** Required
**Body:**
```json
{
  "path": "/current/path.gguf",
  "destination": "internal|external|custom",
  "custom_path": "/optional/custom/path"
}
```

### LLM Manager Core Methods (modules/llm/manager.py)

#### scan_local_models() (lines 151-195)
**Purpose:** Auto-detect dropped model files
**Scans:** `LLM_MODELS_DIR`, `MODELS_DIR`
**Extensions:** .gguf, .safetensors, .bin, .pt, .pth, .onnx
**Caching:** 30-second TTL

**Logic:**
1. Check cache TTL
2. Recursively glob for model files
3. Extract metadata (size, quantization, location)
4. Determine location: INTERNAL/EXTERNAL/CUSTOM
5. Cache results

**Quantization detection:** Regex patterns for Q4_K_M, Q8_0, fp16, etc.

#### list_ollama_models() (lines 226-253)
**Purpose:** List models from Ollama
**API:** GET `{OLLAMA_HOST}/api/tags`

**Response parsing:**
```json
{
  "models": [
    {
      "name": "llama3.2:latest",
      "size": 1234567890,
      "digest": "sha256:...",
      "modified_at": "2024-01-01T00:00:00Z",
      "details": {...}
    }
  ]
}
```

#### pull_ollama_model() (lines 255-277)
**Purpose:** Pull model from Ollama with streaming
**API:** POST `{OLLAMA_HOST}/api/pull`
**Streaming:** NDJSON responses

**Callback support:** Optional progress callback function

**Status updates:**
```json
{"status": "pulling manifest"}
{"status": "downloading digestname", "completed": 123, "total": 456}
{"status": "success"}
```

#### download_from_url() (lines 316-436)
**Purpose:** Download model from any URL
**Threading:** Background daemon thread
**Progress:** 1MB chunks, percentage tracking

**Flow:**
1. Determine filename from URL
2. Select destination directory
3. Create download ID (MD5 hash of URL)
4. Start background thread
5. Track progress in `_downloads` dict
6. Move temp file to final location on completion

**Temp file:** `.{filename}.part` during download

#### delete_local_model() (lines 455-472)
**Purpose:** Delete local model file
**Safety checks:**
- File must exist
- Path must be in allowed model directories
- Updates cache

#### move_model() (lines 501-525)
**Purpose:** Move model to different location
**Checks:**
- Source exists
- Destination doesn't exist
- Creates destination directory

### LLM Data Structures

#### ModelLocation Enum (lines 27-32)
```python
class ModelLocation(Enum):
    INTERNAL = "internal"   # BASE_DIR/models/llm
    EXTERNAL = "external"   # HEAVY_DIR/models/llm
    OLLAMA = "ollama"       # Managed by Ollama
    CUSTOM = "custom"       # User-specified path
```

#### ModelInfo Dataclass (lines 35-63)
```python
@dataclass
class ModelInfo:
    name: str
    path: str
    size_bytes: int
    size_human: str           # "12.3 GB"
    location: ModelLocation
    model_type: str           # gguf, safetensors, ollama
    quantization: str         # Q4_K_M, Q8_0, etc.
    modified: float           # Unix timestamp
    sha256: str
    source_url: str
    metadata: dict
```

**Serialization:** `to_dict()` method for JSON responses

### Frontend State Management (index.html)

#### Global State Object (lines 338-344, 924-927)
```javascript
const state = {
  token: localStorage.getItem('beast_token') || '',
  config: {},              // Loaded from /api/config
  packs: [],               // Loaded from /api/packs
  extensions: [],          // Loaded from /api/extensions
  metrics: {},             // Loaded from /api/metrics
  models: [],              // Loaded from /api/models
  ollamaRunning: false,    // Ollama status
  availableModels: [],     // Library models
  activeDownloads: {}      // Download tracking
};
```

#### Refresh Logic (lines 543-554)
**Function:** `refreshAll()`
**Triggers:** On page load, token save, manual refresh

**Flow:**
1. Check `/api/health`
2. Parallel load:
   - `loadConfig()` → `/api/config`
   - `loadPacks()` → `/api/packs`
   - `loadExtensions()` → `/api/extensions`
   - `loadMetrics()` → `/api/metrics`
   - `refreshModels()` → `/api/models`
3. Render services and capabilities
4. Check service health

#### Auto-refresh (line 1151)
```javascript
setInterval(refreshModels, 30000); // 30 seconds
```

**Purpose:** Detect dropped model files automatically

---

## ⚙️ Settings & Configuration

### Default LLM Configuration

#### Primary Default Model
**File:** `config/features.env` (line 29)
```bash
export FEATURE_AGENT_MODEL_DEFAULT="gpt-5-codex-preview"
```

**Also used in:**
- `apps/agent/core.py` (line 31-34)
- `apps/agent/kryptos_agent.py` (line 21-24)

**Fallback chain:**
1. `AI_BEAST_AGENT_MODEL` env var
2. `FEATURE_AGENT_MODEL_DEFAULT` env var
3. `"llama3.2:latest"` (hardcoded)

#### Ollama Host
**Default:** `http://127.0.0.1:11434`
**Override:** `OLLAMA_HOST` env var
**Used by:** `LLMManager.OLLAMA_HOST`

### Path Configuration (dashboard.py:116-145, manager.py:116-145)

**File:** `config/paths.env`

**Key paths:**
```bash
BASE_DIR          # Project root
GUTS_DIR          # Internal storage (apps, venv)
HEAVY_DIR         # External storage (models, data)
MODELS_DIR        # All models
DATA_DIR          # Data files
OUTPUTS_DIR       # Generated outputs
CACHE_DIR         # Cache files
BACKUP_DIR        # Backups
LOG_DIR           # Logs
COMFYUI_DIR       # ComfyUI installation
VENV_DIR          # Python virtual env
COMFYUI_MODELS_DIR
LLM_MODELS_DIR    # LLM models specifically
LLM_CACHE_DIR     # LLM cache
OLLAMA_MODELS     # Ollama models directory
HF_HOME           # Hugging Face cache
TRANSFORMERS_CACHE
HUGGINGFACE_HUB_CACHE
XDG_CACHE_HOME
TORCH_HOME
```

**Loading logic:**
- Reads from `paths.env`
- Expands `$VAR` references
- Stores in manager instance
- Creates directories if missing

### Port Configuration

**File:** `config/ports.env`

**Core ports:**
```bash
PORT_WEBUI           # Open WebUI
PORT_COMFYUI         # ComfyUI
PORT_QDRANT          # Vector DB
PORT_OLLAMA          # Ollama API
PORT_DASHBOARD       # Dashboard (default 8787)
PORT_N8N             # n8n workflow
PORT_KUMA            # Uptime Kuma
PORT_PORTAINER       # Portainer
PORT_JUPYTER         # JupyterLab
PORT_LANGFLOW        # Langflow
PORT_FLOWISE         # Flowise
PORT_DIFY            # Dify
PORT_TIKA            # Apache Tika
PORT_UNSTRUCTURED    # Unstructured API
PORT_OTEL_GRPC       # OTel gRPC
PORT_OTEL_HTTP       # OTel HTTP
PORT_MINIO           # MinIO API
PORT_MINIO_CONSOLE   # MinIO Console
PORT_SEARXNG         # SearxNG
PORT_SPEECH_API      # Speech API
```

### Feature Flags (config/features.env)

**Total:** 30 flags

**Native services:**
- `FEATURE_NATIVE_OLLAMA=1`
- `FEATURE_NATIVE_COMFYUI=1`
- `FEATURE_NATIVE_DASHBOARD=1`

**Docker services:**
- `FEATURE_DOCKER_QDRANT=1`
- `FEATURE_DOCKER_OPEN_WEBUI=1`
- `FEATURE_DOCKER_UPTIME_KUMA=1`
- `FEATURE_DOCKER_N8N=0`
- `FEATURE_DOCKER_SEARXNG=0`

**Modules:**
- `FEATURE_MODULES_RAG_INGEST=1`

**Extensions:**
- `FEATURE_EXTENSIONS_COMFYUI_MANAGER=1`
- `FEATURE_EXTENSIONS_COMFYUI_VIDEO=1`
- `FEATURE_EXTENSIONS_SEARXNG=1`

**Packs (all disabled by default):**
- `FEATURE_PACKS_NETWORKING=0`
- `FEATURE_PACKS_DEFSEC=0`
- `FEATURE_PACKS_OSINT=0`
- `FEATURE_PACKS_MAPPING=0`
- `FEATURE_PACKS_MEDIA_SYNTH=0`
- `FEATURE_PACKS_SPEECH_STACK=0`
- `FEATURE_PACKS_DATAVIZ_ML=0`
- `FEATURE_PACKS_RESEARCH_HEGEL_ESOTERIC=0`
- `FEATURE_PACKS_AGENT_BUILDERS=0`
- `FEATURE_PACKS_RAG_INGEST_PRO=0`
- `FEATURE_PACKS_OBSERVABILITY_OTEL=0`
- `FEATURE_PACKS_ARTIFACT_STORE_MINIO=0`
- `FEATURE_PACKS_MLX_RUNTIME=0`

**Models:**
- `FEATURE_MODELS_GPT5_CODEX_PREVIEW=1`
- `FEATURE_AGENT_MODEL_DEFAULT="gpt-5-codex-preview"`

### Pack Configurations (config/packs.json)

**Total:** 12 packs

1. **networking**
   - Tools: iperf3, mtr, nmap, curl, wget, socat, tmux
   - Python: scapy, rich

2. **defsec**
   - Tools: clamav, yara, trivy, gitleaks, semgrep, syft, grype
   - Python: bandit, detect-secrets, pip-audit

3. **osint**
   - Tools: ripgrep, fd, pandoc, exiftool, whois, httrack, lynx
   - Python: beautifulsoup4, requests, lxml, trafilatura
   - Docker: searxng extension

4. **mapping**
   - Tools: gdal, geos, proj, tippecanoe, qgis
   - Python: geopandas, shapely, pyproj, rasterio, folium

5. **media_synth**
   - Tools: ffmpeg, imagemagick, sox, flac, lame
   - Python: openai-whisper, faster-whisper, pydub, librosa, moviepy
   - ComfyUI nodes: VideoHelperSuite, Advanced-ControlNet, controlnet_aux, UltimateSDUpscale, Impact-Pack

6. **dataviz_ml**
   - Tools: duckdb, sqlite, graphviz
   - Python: jupyterlab, pandas, numpy, matplotlib, plotly, scikit-learn, polars

7. **research_hegel_esoteric**
   - Tools: pandoc, ripgrep, fd, sqlite, zotero, obsidian
   - Python: pymupdf, pypdf, markdown, python-frontmatter

8. **speech_stack**
   - Tools: cmake, ffmpeg, libsndfile
   - Python: fastapi, uvicorn, faster-whisper, soundfile, pydub
   - Note: Builds whisper.cpp with Metal on macOS

9. **agent_builders**
   - Docker: langflow, flowise, dify extensions
   - Note: Disabled by default

10. **rag_ingest_pro**
    - Docker: Apache Tika, Unstructured API
    - Note: Disabled by default

11. **observability_otel**
    - Docker: otel_collector extension
    - Note: Minimal collector only

12. **artifact_store_minio**
    - Docker: minio extension
    - Note: S3-compatible local storage

**Pack dependencies:** Some packs depend on others (e.g., osint depends on networking)

### Extension Metadata (index.html:346-426)

**EXT_INFO object:** Maps extension names to metadata

**Structure:**
```javascript
{
  title: string,
  description: string,
  ports: [port_keys],
  portal: function(cfg) | string | null,
  api: function(cfg) | string | null
}
```

**Extensions:**
- dify, flowise, langflow (agent builders)
- searxng (meta-search)
- jupyter (notebooks)
- apache_tika, unstructured_api (document parsing)
- otel_collector (telemetry)
- minio (S3 storage)
- comfyui_manager, comfyui_video (ComfyUI add-ons)
- example_service, example_segment (templates)

### Core Services (index.html:428-437)

**CORE_SERVICES array:** 8 essential services

```javascript
[
  { name: 'Open WebUI', port: 'PORT_WEBUI', path: '', api: '/health' },
  { name: 'Ollama API', port: 'PORT_OLLAMA', path: '/api/version', api: '/api/version' },
  { name: 'Qdrant', port: 'PORT_QDRANT', path: '', api: '/healthz' },
  { name: 'ComfyUI', port: 'PORT_COMFYUI', path: '', api: '' },
  { name: 'n8n', port: 'PORT_N8N', path: '', api: '' },
  { name: 'JupyterLab', port: 'PORT_JUPYTER', path: '/lab', api: '/api' },
  { name: 'Uptime Kuma', port: 'PORT_KUMA', path: '', api: '' },
  { name: 'Speech API', port: 'PORT_SPEECH_API', path: '/docs', api: '/docs' }
]
```

### Capabilities System (index.html:439-488)

**CAPABILITIES array:** 4 high-level capabilities

**Structure:**
```javascript
{
  id: string,
  title: string,
  description: string,
  packs: [pack_names],
  extensions: [extension_names],
  portal: function(cfg),
  api: function(cfg),
  health: function(cfg),
  ports: [port_keys],
  notes: string
}
```

**Capabilities:**

1. **text2image**
   - Packs: media_synth
   - Extensions: none
   - Portal: ComfyUI
   - Notes: Requires ComfyUI models

2. **text2video**
   - Packs: media_synth
   - Extensions: comfyui_video
   - Portal: ComfyUI
   - Notes: Requires VideoHelperSuite nodes

3. **text2audio**
   - Packs: speech_stack
   - Extensions: none
   - Portal: Speech API /docs
   - Notes: Start with Speech Up action

4. **text2music**
   - Packs: media_synth, speech_stack
   - Extensions: none
   - Portal: Speech API /docs
   - Notes: Pair with external music models

**Toggle logic:** Auto-enables required packs and extensions

---

## 🔒 Security & Authentication

### API Authentication (dashboard.py:374-379)

**Method:** Token-based via custom header

**Header:** `X-Beast-Token`

**Validation:**
```python
def _auth(self):
    expected = read_token()  # From config/secrets/dashboard_token.txt
    if expected is None:
        return True  # No token = open access
    supplied = self.headers.get("X-Beast-Token", "").strip()
    return secrets.compare_digest(supplied, expected)
```

**Token storage:**
- File: `config/secrets/dashboard_token.txt`
- Frontend: localStorage as `beast_token`

**Protected endpoints:** All `/api/*` except `/api/health`

### Command Execution Whitelist (dashboard.py:30-44)

**ALLOW dict:** Maps keys to allowed command arrays

```python
ALLOW = {
    "init": ["init", "--apply"],
    "preflight": ["preflight"],
    "bootstrap_dry": ["bootstrap", "--dry-run"],
    "bootstrap_apply": ["bootstrap", "--apply"],
    "up": ["up"],
    "down": ["down"],
    "status": ["status"],
    "doctor": ["doctor"],
    "urls": ["urls"],
    "compose_gen": ["compose", "gen", "--apply"],
    "speech_up": ["speech", "up"],
    "speech_down": ["speech", "down"],
    "speech_status": ["speech", "status"],
}
```

**Execution:** All commands run via `bin/beast` only

### Path Sanitization (dashboard.py:93-106)

**Function:** `_sanitize_path(value, label)`

**Checks:**
1. Must be string
2. Cannot be empty
3. No newlines
4. Not prompt text ("Where should", "Enter path", "Default:")
5. Must be absolute path

**Returns:** `(bool, sanitized_path | error_message)`

### Agent Filesystem Constraints (apps/agent/core.py)

**SAFE_SUBDIRS:** Allowed directories for agent operations
```python
{
    "config", "bin", "scripts", "apps", "docker",
    "data", "models", "outputs", "logs", "backups",
    "extensions", ".vscode"
}
```

**Validation:** `is_path_allowed(base, target)` checks:
1. Target is within BASE_DIR
2. First path component is in SAFE_SUBDIRS

**Risky commands:** Blocked unless `--allow-destructive`
```python
RISKY_BINS = {
    "rm", "mv", "dd", "diskutil", "mkfs", "fdisk",
    "shutdown", "reboot", "launchctl", "chown", "chmod", "sudo"
}
```

---

## 📊 Monitoring & Metrics

### Memory Metrics (dashboard.py:162-217)

**Function:** `memory_info()`

**Platforms:**
- macOS: Uses `sysctl` and `vm_stat`
- Linux: Reads `/proc/meminfo`

**Returns:**
```python
{
    "total_gb": float,
    "free_gb": float,
    "used_gb": float,
    "percent_used": float
}
```

### Disk Metrics (dashboard.py:220-228)

**Function:** `load_metrics()` via monitoring module

**Collected:**
- Disk usage (total, used, free, percent)
- Memory stats
- Other system metrics via `modules.monitoring.collect_metrics()`

**Display:** System Metrics card shows:
- Base/Guts/Heavy/Models/Data directories
- Disk used/free (GB and %)
- Memory used/free (GB and %)
- Bind address

### Health Check System (index.html:893-907)

**Function:** `checkHealth()`

**Logic:**
1. Find all elements with `data-health` attribute
2. For each, fetch the health URL
3. Update pill: "ok" (green) or "down" (red)

**Checked services:**
- Capabilities (if defined)
- Custom health endpoints

**Frequency:** On refresh only (not continuous polling)

### Storage Info (index.html:944-960)

**API:** GET `/api/models/storage`

**Displays:**
- Internal storage: free space
- External storage: free space (if different path)

**Update:** On model refresh

---

## 🔄 Data Processing

### RAG Ingest Module (modules/rag/ingest.py)

**Purpose:** Document chunking, embedding, ingestion to Qdrant

**Key functions:**

#### chunk_text() (lines 48-71)
**Parameters:**
- `text`: Input text
- `chunk_size`: Max characters per chunk (default 1200)
- `overlap`: Overlap characters (default 200)

**Logic:**
1. Normalize line endings
2. Split into overlapping windows
3. Strip whitespace

#### embed_text() (lines 102-119)
**Model:** `sentence-transformers/all-MiniLM-L6-v2`

**Process:**
1. Load SentenceTransformer
2. Encode text(s)
3. Return as list of float arrays

**Caching:** Global `_embedder` singleton

#### ingest_file() (line 147+)
**Flow:**
1. Read file with best-effort encoding
2. Chunk text
3. Embed chunks
4. Store in Qdrant collection

**Supported extensions:** Via `iter_files(root, exts)`

### Agent State Schema (apps/agent/state_schema.json)

**Purpose:** Track agent execution history

**Schema:**
```json
{
  "version": integer,
  "last_run": {
    "timestamp": string,
    "model": string,
    "ollama_url": string,
    "apply": boolean,
    "task": string,
    "summary": string,
    "verification": [string],
    "files_touched": [string]
  },
  "notes": [string]
}
```

**File:** `config/agent_state.json`

### Model Metadata Extraction

#### Quantization Detection (manager.py:75-87)
**Patterns:**
```regex
[_-](Q[0-9]_[A-Z0-9_]+)     # Q4_K_M, Q8_0
[_-](q[0-9]_[a-z0-9_]+)     # lowercase variants
[_-](fp16|fp32|f16|f32|bf16)  # Float precision
[_-]([0-9]+bit)             # 8bit, 16bit
```

**Returns:** Normalized uppercase string

#### Model Extension Filtering (manager.py:93)
```python
MODEL_EXTENSIONS = {
    ".gguf", ".safetensors", ".bin",
    ".pt", ".pth", ".onnx"
}
```

**Scan logic:** Recursive glob for `*{ext}` in model directories

---

## ⚠️ CRITICAL FINDINGS: Resume Parsing

### ❌ MISSING FEATURES

**1. No Resume Parsing Functionality**
- Searched patterns: resume, cv, parse, extract
- Found: 35 file mentions, but all unrelated to resume/CV parsing
- **Conclusion:** No dedicated resume parsing exists

**2. No Structured Data Extraction**
- No form field mapping
- No data extraction pipelines for resumes
- No schema definitions for resume data

### ✅ POTENTIAL INTEGRATION PATHS

**1. RAG Ingest Module** (modules/rag/ingest.py)
- Already handles document parsing
- Has chunking and embedding
- **Gap:** Needs structured extraction, not just vector embeddings

**2. Apache Tika Extension** (extensions/apache_tika/)
- Available but not integrated for resume parsing
- Supports many document formats
- **Potential:** Could extract text from PDF/DOCX resumes

**3. Unstructured API Extension** (extensions/unstructured_api/)
- Advanced document chunking
- **Potential:** Could preprocess resumes before extraction

**4. Existing Infrastructure:**
- Agent system with tool execution
- LLM integration (Ollama)
- Vector storage (Qdrant)

### 📋 RECOMMENDED IMPLEMENTATION PLAN

**Phase 1: Document Parsing**
1. Enable Apache Tika extension
2. Create resume upload endpoint
3. Extract raw text from PDF/DOCX

**Phase 2: Structured Extraction**
1. Define resume schema (name, email, phone, education, experience, skills)
2. Use LLM (via Ollama) for entity extraction
3. Map to structured fields

**Phase 3: Storage & Retrieval**
1. Store structured data in database
2. Create resume search API
3. Integrate with existing dashboard

**Phase 4: UI Integration**
1. Add resume upload modal
2. Display parsed fields in form
3. Allow manual corrections

---

## 📈 Metrics & Statistics

### Code Coverage
- **Total audit items:** 73
- **UI elements:** 24 (buttons, inputs, toggles)
- **API endpoints:** 15 (GET: 8, POST: 7)
- **Modal dialogs:** 3
- **LLM manager methods:** 6
- **Configuration files:** 4 (features.env, packs.json, paths.env, ports.env)
- **Packs:** 12
- **Extensions:** 22
- **Core services:** 8
- **Capabilities:** 4

### File Distribution
- **Frontend:** 1 file (index.html, 1155 lines)
- **Backend:** 2 files (dashboard.py 665 lines, manager.py 538 lines)
- **Config:** 4 primary files
- **Modules:** 12+ supporting modules

### Technology Stack
- **Frontend:** Vanilla JavaScript, no framework
- **Backend:** Python 3, SimpleHTTPRequestHandler
- **LLM:** Ollama API, Sentence Transformers
- **Storage:** Filesystem, Qdrant vector DB
- **Docker:** docker-compose for services

---

## 🔍 Next Steps

### Immediate Actions
1. **Confirm findings** with stakeholders
2. **Prioritize** resume parsing implementation
3. **Design** resume data schema
4. **Prototype** extraction with Ollama + Tika

### Long-term Considerations
1. Add automated testing for dashboard
2. Implement user authentication beyond token
3. Create resume parsing documentation
4. Add resume search and filtering
5. Build resume export functionality

---

## Appendix: File References

### Primary Files Audited
- `apps/dashboard/static/index.html` (1155 lines)
- `apps/dashboard/dashboard.py` (665 lines)
- `modules/llm/manager.py` (538 lines)
- `config/features.env` (30 lines)
- `config/packs.json` (341 lines)
- `apps/agent/core.py` (200+ lines examined)
- `modules/rag/ingest.py` (150+ lines examined)
- `apps/agent/state_schema.json` (61 lines)

### Supporting Files
- `config/paths.env`
- `config/ports.env`
- `config/resources/services.json`
- `extensions/*/` (22 extensions)

---

**End of Audit Report**
