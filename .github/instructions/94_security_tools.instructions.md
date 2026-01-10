# Security Tools Instructions (OSINT, SIGINT, OFFSEC, DEFCOM)

### Purpose
Security capabilities encompass offensive security (offsec), defensive operations (defcom), open-source intelligence (OSINT), signals intelligence (SIGINT), forensics, vulnerability scanning, and red/blue team operations.

### Architecture
- **Tool Catalog**: `config/resources/tool_catalog.json` - 200+ security tools
- **Capabilities Registry**: `config/resources/capabilities.json` - capability definitions
- **Tool Registry**: `modules/tools/registry.py` - tool lifecycle management
- **Capabilities Registry**: `modules/capabilities/registry.py` - capability validation
- **Dashboard Integration**: `apps/dashboard/` - WebUI for all tools

### Security Capability Categories

#### OSINT Suite (osint_suite)
Open-source intelligence gathering and reconnaissance.

**Tools Available**:
- `amass` - Attack surface discovery and DNS enumeration
- `subfinder` - Subdomain discovery
- `theharvester` - Email and subdomain harvesting
- `sherlock` - Username reconnaissance
- `holehe` - Email reconnaissance
- `maigret` - Username OSINT
- `spiderfoot` - OSINT automation
- `recon-ng` - Reconnaissance framework
- `waybackurls` - Historical URL collection
- `gau` - URL fetching from multiple sources
- `dnsx` - DNS resolution and probing
- `assetfinder` - Domain asset discovery
- `whois` - Domain registration lookup

**Extensions**: `searxng` (meta-search engine)
**Packs**: `osint`, `networking`

#### SIGINT Suite (sigint_suite)
Signals intelligence and software-defined radio (SDR) operations.

**Tools Available**:
- `rtl_433` - 433MHz signal decoder
- `gnuradio` - Signal processing toolkit
- `gqrx` - SDR receiver GUI
- `sdrangel` - SDR receiver/transceiver
- `kismetdb_dump` - Kismet capture database tool

**Notes**: Requires SDR hardware for live capture; can analyze recorded signals offline.

#### OFFSEC Suite (offsec_suite)
Offensive security tooling for penetration testing and security assessments.

**Tools Available**:
- Network scanning and enumeration
- Web application testing
- Exploitation frameworks
- Password cracking utilities

**Packs**: `defsec`, `networking`
**Notes**: Use only on authorized targets with proper permissions.

#### DEFCON Stack (defcon_stack)
Defensive security and reconnaissance baseline.

**Tools Available**:
- `nmap` - Network mapper and port scanner
- `nuclei` - Vulnerability scanner
- `sqlmap` - SQL injection testing

**Packs**: `defsec`, `networking`

#### Vulnerability Scanning (vuln_scanning)
Automated vulnerability detection and assessment.

**Tools Available**:
- Nuclei templates for CVE scanning
- Web vulnerability scanners
- Dependency checkers

#### Forensics Suite (forensics_suite)
Digital forensics and incident response tools.

**Tools Available**:
- File carving and recovery
- Memory analysis
- Artifact extraction

#### Malware Analysis (malware_analysis)
Malware reverse engineering and behavioral analysis.

**Tools Available**:
- Static analysis tools
- Sandbox environments
- Decompilers and disassemblers

#### Red Team Ops (red_team_ops)
Adversary simulation and offensive operations.

**Capabilities**:
- Command and control (C2) testing
- Social engineering frameworks
- Persistence mechanisms

#### Blue Team Ops (blue_team_ops)
Defensive operations and threat hunting.

**Capabilities**:
- Log analysis
- Threat detection
- Incident response

### Dashboard Integration

All security capabilities are exposed through the dashboard WebUI:

1. **Capability Cards**: Each capability has a card showing:
   - Title and description
   - Required packs and extensions
   - Portal/API links
   - Health checks
   - Action buttons (enable, install, run)

2. **Tool Management**: Tools can be:
   - Discovered from catalog
   - Registered (custom or from catalog)
   - Installed (download + extract or run installer)
   - Tested (validation command or URL check)
   - Executed (with custom arguments)

3. **LLM Integration**: Each capability has "Ask LLM" button that:
   - Sends capability details to Ollama
   - Returns CLI guidance and usage instructions
   - Helps generate tool invocations

4. **Action Types**:
   - `open_url` - Open portal/API in browser
   - `beast_cmd` - Run `bin/beast` command
   - `tool_run` - Execute tool with args
   - `tool_install` - Download and install tool
   - `extension_install` - Install extension
   - `extension_enable` - Enable extension
   - `pack_enable` - Enable pack
   - `ollama_pull` - Pull Ollama model

### Adding New Security Tools

1. **Add to Tool Catalog** (`config/resources/tool_catalog.json`):
```json
{
  "name": "tool_name",
  "category": "osint",
  "description": "Tool description",
  "entrypoint": "tool_name",
  "test_command": "tool_name --version",
  "download_url": "https://example.com/tool.tar.gz"
}
```

2. **Update Capability** (`config/resources/capabilities.json`):
```json
{
  "capabilities": {
    "osint_suite": {
      "checks": [
        {"type": "tool", "name": "tool_name", "tool": "tool_name"}
      ],
      "actions": [
        {"label": "Run tool_name", "type": "tool_run", "tool": "tool_name", "args": "--help"}
      ]
    }
  }
}
```

3. **Tool appears automatically in dashboard** - no code changes needed

### Security and Trust

All security tools respect trust/allowlist policies:
- `config/resources/trust_policy.json` - trust framework
- `config/resources/allowlists.json` - allowed sources
- Tool downloads are validated and extracted safely
- DRYRUN mode prevents accidental execution

### Rules
- **Authorization Required**: Only use security tools on authorized targets
- **DRYRUN by default**: All security tool execution should support dry-run mode
- **Logging**: Security tool runs should be logged for audit trails
- **Isolation**: Consider running security tools in containers or isolated environments
- **Rate Limiting**: Implement rate limiting for network scanning tools
- **Credential Safety**: Never hardcode credentials; use environment variables or vaults

### Usage from Dashboard

1. **Enable Required Packs**:
   - Navigate to "Packs" section
   - Toggle packs: `osint`, `defsec`, `networking`, etc.
   - Click "Apply Changes" to regenerate compose

2. **Install Tools**:
   - Navigate to "Tools" section
   - Use "Tool Catalog" to select tools
   - Click "Add + Install" to register and install
   - Or register custom tool with download URL

3. **Run Capabilities**:
   - Navigate to "Capabilities" section
   - Find desired capability (e.g., "OSINT Suite")
   - Click action buttons (e.g., "Run amass")
   - View output in modal
   - Use "Ask LLM" for guidance

4. **Configure Tool Settings**:
   - Click tool name to open config modal
   - Update entrypoint, args, env variables
   - Save configuration
   - Test with "Test" button

### LLM-Assisted Workflows

The dashboard integrates with Ollama for AI-assisted security operations:

1. **Capability Guidance**: Ask LLM about any capability to get CLI instructions
2. **Output Analysis**: Send tool output to LLM for interpretation
3. **Template Filling**: LLM can fill capability CLI templates
4. **Workflow Generation**: Ask LLM to generate multi-tool workflows

Example prompts:
- "How do I use amass to enumerate subdomains for example.com?"
- "Analyze this nmap output and suggest next steps"
- "Generate a reconnaissance workflow for a web application"

### Verification Commands

Test security tool integration:
```bash
# List all security capabilities
./bin/beast capabilities list --category security

# Check tool availability
./bin/beast tools list --category osint

# Test tool execution (dry-run)
./bin/beast tools run amass --dry-run

# Verify dashboard exposes tools
curl -H "X-Beast-Token: $TOKEN" http://127.0.0.1:8787/api/capabilities
curl -H "X-Beast-Token: $TOKEN" http://127.0.0.1:8787/api/tools/catalog
```

### Common Workflows

**OSINT Reconnaissance**:
1. Enable `osint` pack
2. Install amass, subfinder, theharvester
3. Run subdomain enumeration: `amass enum -d target.com`
4. Collect URLs: `waybackurls target.com`
5. Check DNS: `dnsx -l subdomains.txt`

**Vulnerability Scanning**:
1. Enable `defsec` pack
2. Install nmap, nuclei
3. Port scan: `nmap -sV target.com`
4. Vulnerability scan: `nuclei -u https://target.com`

**SIGINT Analysis**:
1. Enable `sigint` pack (if exists)
2. Install rtl_433, gnuradio
3. Capture signals: `rtl_433 -f 433.92M`
4. Analyze in gnuradio

### Troubleshooting

**Tool Not Found**:
- Check if tool is in catalog: `/api/tools/catalog`
- Verify installation: `which <tool>`
- Check PATH and env variables

**Capability Not Enabled**:
- Enable required packs in dashboard
- Install required extensions
- Check pack status: `./bin/beast packs list`

**Permission Denied**:
- Ensure tool has execute permissions
- Check if running in correct user context
- Review security policies

**LLM Not Responding**:
- Verify Ollama is running: `curl http://127.0.0.1:11434/api/version`
- Check model is pulled: `ollama list`
- Review dashboard token authentication
