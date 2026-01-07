# v11 Resource Graph

Generates a pack→pack→asset→service graph so your plan can answer:
**"why is this required?"**

Outputs:
- `.cache/resource_graph.dot`
- `.cache/resource_graph.md`

Command:
```bash
./bin/beast graph
```

You can render the DOT (optional):
```bash
dot -Tpng .cache/resource_graph.dot -o .cache/resource_graph.png
```
