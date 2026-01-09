# Typed Resources (v13)

These files are optional registries that make the system *explainable*.

- `pack_services.json` (optional): map packs -> docker compose services they introduce.
- `service_urls.json` (optional): service docs URLs or provenance metadata.
- `model_registry.json` (optional): local models you want tracked outside asset packs.

The typed graph generator (`./bin/beast graph typed`) will use these registries when present.
