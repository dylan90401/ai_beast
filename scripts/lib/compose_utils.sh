#!/usr/bin/env bash
set -euo pipefail

# Extract services from a docker-compose YAML file using indentation heuristics.
# Assumes standard compose layout:
# services:
#   svcname:
#     image: ...

compose_list_services() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    BEGIN{in_services=0}
    /^[[:space:]]*services:[[:space:]]*$/ {in_services=1; next}
    in_services==1 && match($0, /^  ([A-Za-z0-9_.-]+):[[:space:]]*$/, m) {print m[1]; next}
    in_services==1 && /^[^ ]/ {in_services=0}
  ' "$file" | sort -u
}

# Emit tab-separated: service<TAB>image
compose_list_service_images() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  awk '
    BEGIN{in_services=0; svc=""}
    /^[[:space:]]*services:[[:space:]]*$/ {in_services=1; next}
    in_services==1 && match($0, /^  ([A-Za-z0-9_.-]+):[[:space:]]*$/, m) {svc=m[1]; next}
    in_services==1 && match($0, /^    image:[[:space:]]*(.+)$/, m) {print svc "\t" m[1]; next}
    in_services==1 && /^[^ ]/ {in_services=0}
  ' "$file"
}

# Best-effort: list compose fragments in extensions
compose_find_fragments() {
  local ext_root="$1"
  [[ -d "$ext_root" ]] || return 0
  find "$ext_root" -type f -name "compose.fragment.yaml" -print 2>/dev/null | sort || true
}
