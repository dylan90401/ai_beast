# Live Toggles (Appliance Behavior)

You can toggle packs/extensions and apply changes without "reinstalling everything".

## Packs (features)
Enable:
```bash
./bin/beast packs enable media_synth osint --apply
./bin/beast live apply --apply
```

Disable (does not uninstall; just toggles off):
```bash
./bin/beast packs disable osint --apply
./bin/beast live apply --apply
```

## Extensions (compose fragments)
```bash
./bin/beast extensions enable grafana_extra --apply
./bin/beast live apply --apply
```

## One command path
```bash
./bin/beast live enable media_synth --apply
```
