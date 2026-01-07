#!/usr/bin/env python3
import argparse, os, sys, hashlib
from pathlib import Path
from typing import Iterable, List, Dict, Any

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def iter_files(root: Path, exts: List[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if exts and p.suffix.lower().lstrip(".") not in exts:
            continue
        yield p

def read_text_best_effort(path: Path, max_bytes: int) -> str:
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    # best effort decode
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc, errors="ignore")
        except Exception:
            pass
    return data.decode("utf-8", errors="ignore")

def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    text = text.replace("\r\n", "\n")
    if chunk_size <= 0:
        return [text]
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        j = min(i + chunk_size, n)
        chunks.append(text[i:j])
        if j == n:
            break
        i = max(0, j - overlap)
    return [c.strip() for c in chunks if c.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="Directory to ingest")
    ap.add_argument("--qdrant", default="http://127.0.0.1:6333", help="Qdrant URL")
    ap.add_argument("--collection", default="ai_beast", help="Collection name")
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2", help="Embedding model")
    ap.add_argument("--chunk-size", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=200)
    ap.add_argument("--max-bytes", type=int, default=2_000_000)
    ap.add_argument("--ext", action="append", default=[], help="Allowed extension (repeat). Example: --ext md --ext txt")
    ap.add_argument("--apply", action="store_true", help="Actually write to Qdrant")
    args = ap.parse_args()

    root = Path(args.dir).expanduser().resolve()
    if not root.exists():
        print(f"[rag] dir not found: {root}", file=sys.stderr)
        sys.exit(2)

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        print("[rag] missing deps. Install: pip install -r modules/rag/requirements.txt", file=sys.stderr)
        raise

    print(f"[rag] qdrant={args.qdrant} collection={args.collection}")
    print(f"[rag] model={args.model} apply={args.apply}")

    client = QdrantClient(url=args.qdrant)

    # Load model
    embedder = SentenceTransformer(args.model)

    # Ensure collection exists
    dim = embedder.get_sentence_embedding_dimension()
    try:
        client.get_collection(args.collection)
        exists = True
    except Exception:
        exists = False

    if not exists:
        if not args.apply:
            print(f"[rag] DRYRUN would create collection '{args.collection}' dim={dim}")
        else:
            client.recreate_collection(
                collection_name=args.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            print(f"[rag] created collection '{args.collection}'")

    exts = [e.lower().lstrip(".") for e in args.ext]
    points = []
    pid = 0
    for f in iter_files(root, exts):
        try:
            text = read_text_best_effort(f, args.max_bytes)
        except Exception as e:
            print(f"[rag] skip read {f}: {e}", file=sys.stderr)
            continue
        chunks = chunk_text(text, args.chunk_size, args.overlap)
        if not chunks:
            continue
        vectors = embedder.encode(chunks, show_progress_bar=False, convert_to_numpy=True)
        for idx, chunk in enumerate(chunks):
            pid += 1
            payload = {
                "path": str(f),
                "chunk_index": idx,
                "text": chunk,
            }
            points.append((pid, vectors[idx].tolist(), payload))

        # flush in batches
        if len(points) >= 128:
            if not args.apply:
                print(f"[rag] DRYRUN would upsert {len(points)} points (latest file: {f})")
                points.clear()
            else:
                client.upsert(
                    collection_name=args.collection,
                    points=[{"id": i, "vector": v, "payload": p} for (i, v, p) in points],
                )
                print(f"[rag] upserted {len(points)} points (latest file: {f})")
                points.clear()

    if points:
        if not args.apply:
            print(f"[rag] DRYRUN would upsert {len(points)} points (final)")
        else:
            client.upsert(
                collection_name=args.collection,
                points=[{"id": i, "vector": v, "payload": p} for (i, v, p) in points],
            )
            print(f"[rag] upserted {len(points)} points (final)")
    print("[rag] done")

if __name__ == "__main__":
    main()
