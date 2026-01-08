# Observability Instructions (doctor, status, logs, healthchecks)

### Rules
- Doctor/preflight outputs must be actionable: include next commands.
- Prefer consistent log prefixes.
- Healthchecks must use `PORT_*` and `127.0.0.1` binds unless LAN is requested.
- Add smoke tests under `scripts/41_smoke_tests.sh` rather than ad-hoc commands.
