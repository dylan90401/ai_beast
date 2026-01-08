# Packs Instructions (compose/packs/, config/packs.json)

Packs are optional capability bundles.

### Source of truth
- `config/packs.json` defines packs and toggles.
- `config/resources/pack_services.json` maps packs to compose services.

### Rules
- Packs are disabled by default unless explicitly enabled.
- Pack fragments should not duplicate base services.
- Any new pack must:
  - register in `config/packs.json`
  - map services in `config/resources/pack_services.json`
  - have a stub compose fragment under `compose/packs/<pack>.yml` if not implemented
  - document required env vars in `.env.example`
