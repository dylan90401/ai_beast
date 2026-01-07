# v9 — Live Toggles + Modular Extensions + Asset Lock/Mirror

## Live toggles
- `./bin/beast live apply --apply` regenerates config + compose and updates running services.
- `./bin/beast live enable <pack> --apply` enables pack + applies immediately.
- `./bin/beast live disable <pack> --apply` disables pack + applies immediately.

## Modular extensions
- `./bin/beast extensions enable <name> --apply`
- Compose fragments are now gated by `extensions/<name>/enabled` **once any enabled markers exist**.

## Assets upgrades
- `./bin/beast assets lock --apply` -> `config/assets.lock.json`
- `./bin/beast assets mirror --to <dir> --apply`
- `./bin/beast assets install ... --mirror=<dir>` uses mirror files instead of downloading.
