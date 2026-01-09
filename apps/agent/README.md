# KRYPTOS Builder Agent (VSCode-friendly)

Local engineering agent that evolves AI Beast using:
- Ollama for reasoning
- deterministic tools (read/write/patch/shell/grep)
- DRYRUN by default, APPLY only when explicitly enabled

## Install
From workspace root:

```bash
python3 -m venv apps/agent/.venv
source apps/agent/.venv/bin/activate
pip3 install -r apps/agent/requirements.txt
```

## Run (single-agent)
Dry-run:
```bash
python3 apps/agent/kryptos_agent.py "Run preflight and propose next improvements."
```

Apply changes:
```bash
python3 apps/agent/kryptos_agent.py --apply "Implement rag_ingest_pro minimal pipeline and add beast ingest run/watch."
```

## Run (multi-agent)
Supervisor → Implementer → Verifier:
```bash
python3 apps/agent/kryptos_agent_multi.py "Refactor compose generation to be more deterministic and add verification."
```

Apply mode:
```bash
python3 apps/agent/kryptos_agent_multi.py --apply "Implement feature X and verify."
```

## State memory
The agent stores non-sensitive run summaries here:
- `config/agent_state.json`

## VSCode
See `.vscode/tasks.json` for one-click runs (Preflight / Status / Agent DRYRUN / Agent APPLY).


## Multi-agent (Supervisor → Implementer → Verifier)

The multi-agent orchestrator now runs the Verifier as a real tool-using loop (shell/curl/grep), **always non-destructive** (APPLY is ignored for the verifier).

Run:
```bash
python3 apps/agent/kryptos_agent_multi.py "Plan + implement + verify..."
```


## Multi-agent pipelines (v24)

Run a named pipeline:

```bash
# default: supervisor -> implementer(tool) -> verifier(tool)
python3 apps/agent/kryptos_agent_hub.py --pipeline build "Run preflight, fix issues, verify status."

# harden: adds auditor + verifier_strict (read-only)
python3 apps/agent/kryptos_agent_hub.py --pipeline harden "Audit for hardcoded ports/paths and propose fixes."

# docs: supervisor -> docs(tool)
python3 apps/agent/kryptos_agent_hub.py --pipeline docs "Update README quickstart to match current CLI."
```

## Strict deterministic verification (no LLM)

```bash
python3 apps/agent/verifier_strict.py
```

This runs:
- `./bin/beast preflight --verbose`
- `./bin/beast status --verbose`
- curl checks for Ollama/Qdrant/ComfyUI/WebUI (best-effort)
- `./bin/beast compose gen --dry-run --verbose`
