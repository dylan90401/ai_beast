#!/usr/bin/env bash
set -euo pipefail

PLAN=""
GRAPH=""
OUT_DIR=""

for arg in "${@:-}"; do
  case "$arg" in
    --plan=*) PLAN="${arg#--plan=}" ;;
    --graph=*) GRAPH="${arg#--graph=}" ;;
    --out=*) OUT_DIR="${arg#--out=}" ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$script_dir/.." && pwd)"

PLAN="${PLAN:-$BASE_DIR/.cache/state.plan.json}"
GRAPH="${GRAPH:-$BASE_DIR/.cache/typed_graph.json}"
OUT_DIR="${OUT_DIR:-$BASE_DIR/.cache}"

mkdir -p "$OUT_DIR"

json_out="$OUT_DIR/plan.reasoned.json"
md_out="$OUT_DIR/plan.reasoned.md"

PLAN_PATH="$PLAN" GRAPH_PATH="$GRAPH" JSON_OUT="$json_out" MD_OUT="$md_out" python3 - <<'PY'
import os, json, pathlib, collections

plan_path = pathlib.Path(os.environ["PLAN_PATH"])
graph_path = pathlib.Path(os.environ["GRAPH_PATH"])
json_out = pathlib.Path(os.environ["JSON_OUT"])
md_out = pathlib.Path(os.environ["MD_OUT"])

plan = json.loads(plan_path.read_text(encoding="utf-8"))
graph = json.loads(graph_path.read_text(encoding="utf-8"))

nodes = {n["id"]: n for n in graph.get("nodes", [])}
name_to_id = {}
for n in graph.get("nodes", []):
    name_to_id[(n["type"], n["name"])] = n["id"]

# adjacency for BFS (directed)
adj = collections.defaultdict(list)
for e in graph.get("edges", []):
    adj[e["from"]].append((e["to"], e.get("rel","")))

# Find state node id
state_id = None
for n in graph.get("nodes", []):
    if n.get("type") == "state":
        state_id = n["id"]
        break

def pretty_node(nid: str) -> str:
    n = nodes.get(nid, {})
    return f'{n.get("type","?")}:{n.get("name","?")}'

def shortest_path(src, dst):
    if src is None:
        return None
    q = collections.deque([src])
    prev = {src: None}
    prev_rel = {}
    while q:
        cur = q.popleft()
        if cur == dst:
            break
        for nxt, rel in adj.get(cur, []):
            if nxt not in prev:
                prev[nxt] = cur
                prev_rel[nxt] = rel
                q.append(nxt)
    if dst not in prev:
        return None
    # reconstruct
    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    rels = []
    for i in range(1, len(path)):
        rels.append(prev_rel.get(path[i], ""))
    return path, rels

def reason_for(t, name):
    tid = name_to_id.get((t, name))
    if not tid:
        return None, None, None
    sp = shortest_path(state_id, tid)
    if not sp:
        return tid, None, None
    path, rels = sp
    # build readable chain
    parts = [pretty_node(path[0])]
    for i in range(1, len(path)):
        parts.append(f'--{rels[i-1]}--> {pretty_node(path[i])}')
    return tid, path, " ".join(parts)

def annotate_list(kind, items, node_type):
    out=[]
    for it in items or []:
        if isinstance(it, dict):
            name = it.get("pack") or it.get("name") or ""
        else:
            name = it
        nid, path, chain = reason_for(node_type, name)
        o = {"value": it, "node_id": nid, "reason_chain": chain}
        out.append(o)
    return out

reasoned = {
    "generated_at": plan.get("generated_at"),
    "state_file": plan.get("state_file"),
    "diff": {
        "packs_enable": annotate_list("packs_enable", plan["diff"].get("packs_enable"), "pack"),
        "packs_disable": annotate_list("packs_disable", plan["diff"].get("packs_disable"), "pack"),
        "extensions_enable": annotate_list("extensions_enable", plan["diff"].get("extensions_enable"), "extension"),
        "extensions_disable": annotate_list("extensions_disable", plan["diff"].get("extensions_disable"), "extension"),
        "assets_install": annotate_list("assets_install", plan["diff"].get("assets_install"), "asset_pack"),
    },
    "runtime": plan.get("runtime", {}),
    "options": plan.get("options", {}),
    "graph": {
        "typed_graph": str(graph_path),
    }
}

json_out.write_text(json.dumps(reasoned, indent=2) + "
", encoding="utf-8")

# markdown
md=[]
md.append("# Reasoned Execution Plan (v13)")
md.append("")
md.append(f"Generated: {reasoned['generated_at']} UTC")
md.append("")
def sec(title, arr):
    md.append(f"## {title}")
    if not arr:
        md.append("- (none)")
        md.append("")
        return
    for x in arr:
        md.append(f"- `{x['value']}`")
        if x.get("node_id"):
            md.append(f"  - node_id: `{x['node_id']}`")
        if x.get("reason_chain"):
            md.append(f"  - why: {x['reason_chain']}")
    md.append("")

sec("Enable Packs", reasoned["diff"]["packs_enable"])
sec("Disable Packs", reasoned["diff"]["packs_disable"])
sec("Enable Extensions", reasoned["diff"]["extensions_enable"])
sec("Disable Extensions", reasoned["diff"]["extensions_disable"])
sec("Install Asset Packs", reasoned["diff"]["assets_install"])

md.append("## Notes")
md.append(f"- Typed graph: `{graph_path}`")
md_out.write_text("
".join(md) + "
", encoding="utf-8")
PY

echo "[plan:reasoned] Wrote $json_out and $md_out"
