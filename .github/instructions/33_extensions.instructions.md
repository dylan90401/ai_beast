# Extensions Instructions (extensions/)

Each extension must follow the contract:
- `install.sh` required
- DRYRUN by default; supports `--apply`
- must not hardcode paths; must source `config/paths.env`
- compose fragment: `compose.fragment.yaml` (or `.yml`) must be renderable by the compose pipeline

### Stub discipline
If extension is stubbed:
- Provide a minimal `compose.fragment.yaml` that validates.
- Provide a README with:
  - purpose
  - required env vars
  - enable/disable instructions
