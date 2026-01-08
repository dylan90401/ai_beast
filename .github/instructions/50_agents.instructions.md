# Agents Instructions (apps/agent/)

### Purpose
Agents help keep the repo buildable and runnable.

### Tool protocol (autonomous runner)
- Tool actions: one JSON object per line: `{"tool":"...","args":{...}}`
- Final response: `{"final":"..."}`
- No tool calls in markdown fences.

### Role separation
- Auditor: detect drift/missing pieces/policy violations
- Implementer: minimal changes + tests
- Verifier: run checks + report concrete results

### Playbooks / pipelines
- Playbooks: `apps/agent/playbooks/`
- Pipelines: `apps/agent/pipelines/`
- Every playbook includes verification steps.

## Refactoring contract (behavior-preserving unless requested)
- Prefer incremental refactors (small units), not mega rewrites.
- Keep public surfaces stable: CLI flags, env var names, service names, output formats.
- Extract helpers only when duplication exists in ≥2 places.
- Add/adjust tests or assertions to lock behavior.
- Finish with verification (see repo DoD).
