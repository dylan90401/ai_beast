# Extensions (Modular Segments)

Extensions are drop-in modules under `extensions/<name>/`.

## Files an extension may include
- `compose.fragment.yaml` — docker compose fragment
- `README.md` — notes
- `enabled` — marker file (created when enabled)

## Toggle extensions
```bash
./bin/beast extensions list
./bin/beast extensions enable <name> --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Compatibility mode
If **no** `extensions/*/enabled` markers exist, `compose gen` includes **all** fragments (legacy behavior).
Once you enable any extension, only enabled ones are included.
