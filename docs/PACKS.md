# Feature Packs (Post-install)

Packs install *optional* toolchains in an idempotent, DRYRUN-first way.

List packs:
```bash
./bin/beast packs list
```

Install one pack:
```bash
./bin/beast packs install osint --apply
```

Install all:
```bash
./bin/beast packs install all --apply
```

Each pack can:
- install Homebrew formulae + casks
- create a dedicated Python venv at `.venv_packs/<pack>/`
- seed directories under `DATA_DIR`
- optionally enable docker profiles (via `config/features.local.yml` overrides)

After any pack toggles docker features, regenerate compose and start:
```bash
./bin/beast compose gen --apply
./bin/beast up
```
