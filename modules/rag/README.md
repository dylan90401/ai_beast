# RAG (Qdrant + local embeddings)

This module ingests files from a directory into Qdrant.

Requirements (install into the AI Beast venv):
```bash
source "$VENV_DIR/bin/activate"
pip install -r modules/rag/requirements.txt
```

Run:
```bash
./bin/beast rag ingest --dir "$DATA_DIR/inbox" --collection ai_beast --apply
```
