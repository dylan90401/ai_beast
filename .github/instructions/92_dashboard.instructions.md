# Dashboard Instructions (apps/dashboard)

### Purpose
The Dashboard is the central WebUI control panel for the entire AI Beast stack. It provides a unified interface for managing tools, capabilities, packs, extensions, services, and LLM-assisted operations.

### Architecture
- **Backend**: `apps/dashboard/dashboard.py` - Python HTTP server with REST API
- **Frontend**: `apps/dashboard/static/index.html` - Single-page app with vanilla JS
- **Port**: `PORT_DASHBOARD` (default 8787) from `config/ports.env`
- **Auth**: Token-based via `config/secrets/dashboard_token.txt` (X-Beast-Token header)
- **Base Dir**: Auto-detected from `BASE_DIR` or resolved from project structure

### Key Features

#### 1. Capability Management
All capabilities (text2image, OSINT, SIGINT, OFFSEC, etc.) are exposed with:
- Enable/disable packs and extensions
- Health checks (HTTP, TCP, tool, Ollama model)
- Action buttons (open portal, run tool, install dependencies)
- LLM integration for CLI guidance

#### 2. Tool Registry
Tools from `config/resources/tool_catalog.json` can be:
- Browsed by category (osint, sigint, security, etc.)
- Registered from catalog or custom URL
- Installed (download tar.gz or run installer)
- Tested (validation command or URL)
- Executed with custom arguments
- Configured (entrypoint, args, env, workflow)

#### 3. LLM Integration
Ollama integration for AI-assisted operations:
- `/api/llm/analyze` endpoint sends prompts to Ollama
- "Ask LLM" buttons on capabilities for CLI guidance
- Output analysis and interpretation
- Template filling for capability workflows

#### 4. Pack and Extension Control
Toggle packs and extensions with apply workflow:
- Enable/disable packs (e.g., `osint`, `defsec`, `networking`)
- Install extensions (e.g., `searxng`, `jupyter`)
- Trigger compose regeneration and service restart

#### 5. System Monitoring
Real-time metrics and status:
- Memory usage (total, used, free, percent)
- Disk usage per directory
- Service health checks
- Port mappings and URLs

### API Endpoints

**Configuration & Status**:
- `GET /api/health` - Health check (no auth)
- `GET /api/config` - Environment config (paths, ports)
- `GET /api/metrics` - System metrics (memory, disk)

**Capabilities & Tools**:
- `GET /api/capabilities` - List all capabilities with metadata
- `GET /api/tools/list` - List registered tools
- `GET /api/tools/catalog` - List tool catalog (uninstalled tools)
- `POST /api/tools/register` - Register tool from catalog or custom
- `POST /api/tools/install` - Install tool
- `POST /api/tools/run` - Execute tool with args
- `POST /api/tools/test` - Run tool test command
- `POST /api/tools/update` - Update tool config
- `POST /api/capabilities/template` - Save capability CLI template

**Packs & Extensions**:
- `GET /api/packs` - List packs with enabled status
- `GET /api/extensions` - List extensions with metadata
- `POST /api/toggle` - Enable/disable pack or extension
- `POST /api/extensions/install` - Install extension

**Services & Operations**:
- `GET /api/services` - List all services with ports
- `POST /api/services/logs` - Get service logs (docker or native)
- `GET /api/run?cmd=<key>` - Run beast command (preflight, status, etc.)

**LLM**:
- `POST /api/llm/analyze` - Send prompt to Ollama, get response
- `POST /api/models/pull` - Pull Ollama model

### Security Tool Integration

The dashboard fully exposes all security capabilities:

**OSINT Suite** (`osint_suite`):
- Tools: amass, subfinder, theharvester, sherlock, waybackurls, etc.
- Extension: searxng (meta-search)
- Actions: Run tool, install tool, open SearXNG portal

**SIGINT Suite** (`sigint_suite`):
- Tools: rtl_433, gnuradio, gqrx, sdrangel
- Actions: Run SDR tools, check availability

**OFFSEC Suite** (`offsec_suite`):
- Tools: Various offensive security utilities
- Actions: Run tools with authorization checks

**DEFCON Stack** (`defcon_stack`):
- Tools: nmap, nuclei, sqlmap
- Actions: Run scans, enable defsec pack

**Other Security Capabilities**:
- Vulnerability Scanning
- Forensics Suite
- Malware Analysis
- Red Team Ops
- Blue Team Ops

All tools support:
- LLM-assisted execution ("Ask LLM" for usage guidance)
- Custom argument passing
- Output capture and modal display
- Integration with capability workflows

### Frontend Architecture

Single-page app with sections:
1. **Auth & Health** - Token input, health indicator, refresh button
2. **System Metrics** - Paths, memory, disk usage
3. **Actions** - Quick commands (preflight, status, up, down, etc.)
4. **Storage Paths** - Update GUTS_DIR and HEAVY_DIR
5. **Capabilities** - Full capability cards with actions
6. **Tools** - Tool catalog, registration, management
7. **Features** - Feature flags (from config/features.yml)
8. **Runtime Settings** - Profile, docker runtime
9. **Packs** - Pack toggles
10. **Extensions** - Extension toggles and install
11. **Services & Ports** - Service list with links
12. **Command Output** - Terminal-style log display

Modals:
- **Console Output** - Full command output with LLM analysis
- **Capability Details** - Detailed capability info with CLI template
- **Tool Configuration** - Tool settings editor

### Rules
- Keep dashboard lightweight; avoid heavy deps without approval.
- Any service links must use `PORT_*` from environment config.
- Prefer static assets in `apps/dashboard/static/`.
- Never hardcode ports or paths; always load from `/api/config`.
- Maintain single-file HTML+CSS+JS for portability.
- Use token auth for all mutating operations.
- Log all tool executions for audit trail.
- Support DRYRUN mode where applicable.

### Adding New Dashboard Features

1. **Backend API Endpoint**: Add handler to `dashboard.py`:
```python
def do_POST(self):
    if p.path == "/api/new/endpoint":
        if not self._auth():
            return self._json(401, {"ok": False, "error": "Unauthorized"})
        # handle request
        return self._json(200, {"ok": True, "data": result})
```

2. **Frontend Function**: Add to `index.html` script:
```javascript
async function newFeature() {
    const data = await apiPost('/api/new/endpoint', {param: value});
    if (data.ok) {
        setLog('Success!');
    }
}
```

3. **UI Element**: Add to appropriate section:
```html
<button class="btn" onclick="newFeature()">New Feature</button>
```

### Testing Dashboard

```bash
# Start dashboard
./bin/beast dashboard

# Check health
curl http://127.0.0.1:8787/api/health

# With token auth
export TOKEN=$(cat config/secrets/dashboard_token.txt)
curl -H "X-Beast-Token: $TOKEN" http://127.0.0.1:8787/api/config

# Test capability list
curl -H "X-Beast-Token: $TOKEN" http://127.0.0.1:8787/api/capabilities

# Test tool execution
curl -X POST -H "X-Beast-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"nmap","args":"--version"}' \
  http://127.0.0.1:8787/api/tools/run

# Test LLM integration
curl -X POST -H "X-Beast-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt":"How do I use amass for subdomain enumeration?"}' \
  http://127.0.0.1:8787/api/llm/analyze
```

### Troubleshooting

**Dashboard Won't Start**:
- Check `PORT_DASHBOARD` is not in use: `lsof -i :8787`
- Verify `BASE_DIR` is set correctly
- Check logs: `tail -f logs/dashboard.out.log`

**Tools Not Appearing**:
- Verify `config/resources/tool_catalog.json` exists
- Check API response: `/api/tools/catalog`
- Refresh browser cache

**LLM Not Responding**:
- Check Ollama is running: `curl http://127.0.0.1:11434/api/version`
- Verify model is available: `ollama list`
- Check `PORT_OLLAMA` in config

**Auth Failing**:
- Verify token file exists: `cat config/secrets/dashboard_token.txt`
- Check browser localStorage for saved token
- Regenerate token if needed
