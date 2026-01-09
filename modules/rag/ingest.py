#!/usr/bin/env python3
"""RAG ingestion module for AI Beast.

Provides document chunking, embedding, and ingestion to Qdrant vector store.
"""
import argparse
import hashlib
import sys
from collections.abc import Iterable
from pathlib import Path

# Lazy-loaded dependencies
_embedder = None
_qdrant_client = None


def sha256_bytes(b: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(b).hexdigest()


def iter_files(root: Path, exts: list[str]) -> Iterable[Path]:
    """Iterate over files in directory, optionally filtering by extension."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if exts and p.suffix.lower().lstrip(".") not in exts:
            continue
        yield p


def read_text_best_effort(path: Path, max_bytes: int = 2_000_000) -> str:
    """Read text file with best-effort encoding detection."""
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


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for embedding.

    Args:
        text: Text to chunk
        chunk_size: Maximum characters per chunk
        overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks
    """
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


def get_embedder(model: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """Get or create a cached embedding model instance."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer(model)
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers required. Install: pip3 install sentence-transformers"
            ) from exc
    return _embedder


def get_qdrant_client(url: str = "http://127.0.0.1:6333"):
    """Get or create a cached Qdrant client instance."""
    global _qdrant_client
    if _qdrant_client is None:
        try:
            from qdrant_client import QdrantClient
            _qdrant_client = QdrantClient(url=url)
        except ImportError as exc:
            raise ImportError(
                "qdrant-client required. Install: pip3 install qdrant-client"
            ) from exc
    return _qdrant_client


def embed_text(
    text: str | list[str],
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> list[list[float]]:
    """Embed text using sentence transformers.

    Args:
        text: Single text string or list of strings to embed
        model: Name of the sentence-transformers model

    Returns:
        List of embedding vectors (list of floats)
    """
    embedder = get_embedder(model)
    if isinstance(text, str):
        text = [text]
    vectors = embedder.encode(text, show_progress_bar=False, convert_to_numpy=True)
    return [v.tolist() for v in vectors]


def ensure_collection(
    client,
    collection_name: str,
    vector_size: int,
    distance: str = "Cosine",
) -> bool:
    """Ensure a Qdrant collection exists, create if not.

    Returns:
        True if collection was created, False if it existed
    """
    from qdrant_client.http.models import Distance, VectorParams

    try:
        client.get_collection(collection_name)
        return False
    except Exception:
        dist = getattr(Distance, distance.upper(), Distance.COSINE)
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=dist),
        )
        return True


def ingest_file(
    path: str | Path,
    collection: str = "ai_beast",
    qdrant_url: str = "http://127.0.0.1:6333",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    chunk_size: int = 1200,
    overlap: int = 200,
    max_bytes: int = 2_000_000,
    apply: bool = False,
) -> dict:
    """Ingest a single file into Qdrant.

    Args:
        path: Path to the file
        collection: Qdrant collection name
        qdrant_url: Qdrant server URL
        model: Embedding model name
        chunk_size: Characters per chunk
        overlap: Overlap between chunks
        max_bytes: Maximum file size to read
        apply: If False, dry-run mode

    Returns:
        Dict with status and statistics
    """
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return {"ok": False, "error": f"File not found: {path}"}

    try:
        text = read_text_best_effort(path, max_bytes)
    except Exception as e:
        return {"ok": False, "error": f"Failed to read file: {e}"}

    chunks = chunk_text(text, chunk_size, overlap)
    if not chunks:
        return {"ok": True, "chunks": 0, "message": "No content to ingest"}

    vectors = embed_text(chunks, model)

    if not apply:
        return {
            "ok": True,
            "dryrun": True,
            "chunks": len(chunks),
            "vector_dim": len(vectors[0]) if vectors else 0,
            "message": f"Would ingest {len(chunks)} chunks from {path.name}",
        }

    client = get_qdrant_client(qdrant_url)
    dim = len(vectors[0])
    ensure_collection(client, collection, dim)

    # Generate point IDs based on file hash
    file_hash = sha256_bytes(path.read_bytes())[:12]
    points = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        point_id = int(hashlib.md5(f"{file_hash}:{idx}".encode()).hexdigest()[:15], 16)
        points.append({
            "id": point_id,
            "vector": vector,
            "payload": {
                "path": str(path),
                "filename": path.name,
                "chunk_index": idx,
                "text": chunk,
                "file_hash": file_hash,
            },
        })

    client.upsert(collection_name=collection, points=points)

    return {
        "ok": True,
        "chunks": len(chunks),
        "vector_dim": dim,
        "message": f"Ingested {len(chunks)} chunks from {path.name}",
    }


def ingest_directory(
    directory: str | Path,
    collection: str = "ai_beast",
    qdrant_url: str = "http://127.0.0.1:6333",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    chunk_size: int = 1200,
    overlap: int = 200,
    max_bytes: int = 2_000_000,
    extensions: list[str] | None = None,
    apply: bool = False,
) -> dict:
    """Ingest all files in a directory into Qdrant.

    Args:
        directory: Path to directory
        collection: Qdrant collection name
        qdrant_url: Qdrant server URL
        model: Embedding model name
        chunk_size: Characters per chunk
        overlap: Overlap between chunks
        max_bytes: Max file size to read
        extensions: List of file extensions to include (e.g., ['md', 'txt'])
        apply: If False, dry-run mode

    Returns:
        Dict with status and statistics
    """
    directory = Path(directory).expanduser().resolve()
    if not directory.exists():
        return {"ok": False, "error": f"Directory not found: {directory}"}

    exts = [e.lower().lstrip(".") for e in (extensions or [])]

    results = {"ok": True, "files": 0, "chunks": 0, "errors": [], "dryrun": not apply}

    for fpath in iter_files(directory, exts):
        result = ingest_file(
            path=fpath,
            collection=collection,
            qdrant_url=qdrant_url,
            model=model,
            chunk_size=chunk_size,
            overlap=overlap,
            max_bytes=max_bytes,
            apply=apply,
        )
        if result.get("ok"):
            results["files"] += 1
            results["chunks"] += result.get("chunks", 0)
        else:
            results["errors"].append({"file": str(fpath), "error": result.get("error")})

    results["message"] = f"{'Ingested' if apply else 'Would ingest'} {results['chunks']} chunks from {results['files']} files"
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="Directory to ingest")
    ap.add_argument("--qdrant", default="http://127.0.0.1:6333", help="Qdrant URL")
    ap.add_argument("--collection", default="ai_beast", help="Collection name")
    ap.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Embedding model",
    )
    ap.add_argument("--chunk-size", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=200)
    ap.add_argument("--max-bytes", type=int, default=2_000_000)
    ap.add_argument(
        "--ext",
        action="append",
        default=[],
        help="Allowed extension (repeat). Example: --ext md --ext txt",
    )
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
    except Exception:
        print(
            "[rag] missing deps. Install: pip3 install -r modules/rag/requirements.txt",
            file=sys.stderr,
        )
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
        vectors = embedder.encode(
            chunks, show_progress_bar=False, convert_to_numpy=True
        )
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
                print(
                    f"[rag] DRYRUN would upsert {len(points)} points (latest file: {f})"
                )
                points.clear()
            else:
                client.upsert(
                    collection_name=args.collection,
                    points=[
                        {"id": i, "vector": v, "payload": p} for (i, v, p) in points
                    ],
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
