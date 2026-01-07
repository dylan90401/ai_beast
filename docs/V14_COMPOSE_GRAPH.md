# v14: Graph-driven compose selection + minimal drift reconcile

## What changed vs v13
v14 makes **compose generation** depend on **desired state** (packs/extensions/services) instead of blindly
including every enabled fragment.

Key idea:
- Desired state → (packs + deps) → services (via config/resources/pack_services.json)
- Desired state → extensions → services (via scanning compose.fragment.yaml)
- Services → fragments (via scanning fragments)
- Compose = base + ops + *only needed fragments*

It also upgrades drift:
- drift is evaluated at **service** granularity
- apply reconciles **only drifting services** (pull/recreate) instead of nuking everything
- drift output includes a "why" chain (pack/extension roots) when possible
