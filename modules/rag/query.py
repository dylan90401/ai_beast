#!/usr/bin/env python3
"""RAG query module for AI Beast.

Provides semantic search and retrieval from Qdrant vector store.
"""
import argparse
import sys

from .ingest import embed_text, get_qdrant_client


def search(
    query: str,
    collection: str = "ai_beast",
    qdrant_url: str = "http://127.0.0.1:6333",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    limit: int = 5,
    score_threshold: float | None = None,
    filter_payload: dict | None = None,
) -> dict:
    """Search for similar documents in Qdrant.

    Args:
        query: Search query text
        collection: Qdrant collection name
        qdrant_url: Qdrant server URL
        model: Embedding model name (must match ingestion model)
        limit: Maximum number of results
        score_threshold: Minimum similarity score (0-1 for cosine)
        filter_payload: Qdrant filter conditions

    Returns:
        Dict with search results and metadata
    """
    if not query.strip():
        return {"ok": False, "error": "Empty query"}

    try:
        # Embed the query
        vectors = embed_text(query, model)
        query_vector = vectors[0]

        # Get client and search
        client = get_qdrant_client(qdrant_url)

        search_params = {
            "collection_name": collection,
            "query_vector": query_vector,
            "limit": limit,
        }

        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        if filter_payload:
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue
            # Simple filter support - extend as needed
            conditions = []
            for key, value in filter_payload.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            if conditions:
                search_params["query_filter"] = Filter(must=conditions)

        results = client.search(**search_params)

        hits = []
        for hit in results:
            hits.append({
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "path": hit.payload.get("path", ""),
                "filename": hit.payload.get("filename", ""),
                "chunk_index": hit.payload.get("chunk_index", 0),
                "payload": hit.payload,
            })

        return {
            "ok": True,
            "query": query,
            "collection": collection,
            "count": len(hits),
            "results": hits,
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_context(
    query: str,
    collection: str = "ai_beast",
    qdrant_url: str = "http://127.0.0.1:6333",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    limit: int = 5,
    max_tokens: int = 4000,
    separator: str = "\n\n---\n\n",
) -> dict:
    """Get context for RAG by searching and concatenating results.

    This is a convenience function for building LLM context from
    retrieved documents.

    Args:
        query: Search query text
        collection: Qdrant collection name
        qdrant_url: Qdrant server URL
        model: Embedding model name
        limit: Maximum number of chunks to retrieve
        max_tokens: Approximate max characters for context
        separator: String to join chunks

    Returns:
        Dict with concatenated context and metadata
    """
    result = search(
        query=query,
        collection=collection,
        qdrant_url=qdrant_url,
        model=model,
        limit=limit,
    )

    if not result.get("ok"):
        return result

    chunks = []
    total_len = 0
    sources = []

    for hit in result.get("results", []):
        text = hit.get("text", "")
        if total_len + len(text) > max_tokens:
            break
        chunks.append(text)
        total_len += len(text) + len(separator)
        sources.append({
            "path": hit.get("path", ""),
            "filename": hit.get("filename", ""),
            "score": hit.get("score", 0),
        })

    context = separator.join(chunks)

    return {
        "ok": True,
        "query": query,
        "context": context,
        "context_length": len(context),
        "chunks_used": len(chunks),
        "sources": sources,
    }


def list_collections(qdrant_url: str = "http://127.0.0.1:6333") -> dict:
    """List all collections in Qdrant.

    Returns:
        Dict with list of collections and their info
    """
    try:
        client = get_qdrant_client(qdrant_url)
        collections = client.get_collections()

        items = []
        for col in collections.collections:
            try:
                info = client.get_collection(col.name)
                items.append({
                    "name": col.name,
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "status": str(info.status),
                    "vector_size": info.config.params.vectors.size if hasattr(info.config.params, 'vectors') else None,
                })
            except Exception:
                items.append({
                    "name": col.name,
                    "status": "unknown",
                })

        return {"ok": True, "collections": items}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def collection_info(
    collection: str = "ai_beast",
    qdrant_url: str = "http://127.0.0.1:6333",
) -> dict:
    """Get detailed info about a collection.

    Returns:
        Dict with collection statistics and configuration
    """
    try:
        client = get_qdrant_client(qdrant_url)
        info = client.get_collection(collection)

        return {
            "ok": True,
            "name": collection,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "status": str(info.status),
            "optimizer_status": str(info.optimizer_status),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_collection(
    collection: str,
    qdrant_url: str = "http://127.0.0.1:6333",
    apply: bool = False,
) -> dict:
    """Delete a collection from Qdrant.

    Args:
        collection: Collection name to delete
        qdrant_url: Qdrant server URL
        apply: If False, dry-run mode

    Returns:
        Dict with operation status
    """
    if not apply:
        return {
            "ok": True,
            "dryrun": True,
            "message": f"Would delete collection '{collection}'",
        }

    try:
        client = get_qdrant_client(qdrant_url)
        client.delete_collection(collection)
        return {
            "ok": True,
            "message": f"Deleted collection '{collection}'",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    """CLI entry point for RAG query."""
    ap = argparse.ArgumentParser(description="Query Qdrant vector store")
    ap.add_argument("query", nargs="?", help="Search query text")
    ap.add_argument("--qdrant", default="http://127.0.0.1:6333", help="Qdrant URL")
    ap.add_argument("--collection", default="ai_beast", help="Collection name")
    ap.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Embedding model",
    )
    ap.add_argument("--limit", type=int, default=5, help="Max results")
    ap.add_argument("--list", action="store_true", help="List all collections")
    ap.add_argument("--info", action="store_true", help="Show collection info")
    ap.add_argument("--context", action="store_true", help="Get RAG context")
    ap.add_argument("--delete", action="store_true", help="Delete collection")
    ap.add_argument("--apply", action="store_true", help="Apply destructive operations")
    args = ap.parse_args()

    import json

    if args.list:
        result = list_collections(args.qdrant)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if args.info:
        result = collection_info(args.collection, args.qdrant)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if args.delete:
        result = delete_collection(args.collection, args.qdrant, args.apply)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if not args.query:
        ap.print_help()
        sys.exit(1)

    if args.context:
        result = get_context(
            query=args.query,
            collection=args.collection,
            qdrant_url=args.qdrant,
            model=args.model,
            limit=args.limit,
        )
    else:
        result = search(
            query=args.query,
            collection=args.collection,
            qdrant_url=args.qdrant,
            model=args.model,
            limit=args.limit,
        )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
