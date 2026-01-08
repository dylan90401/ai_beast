#!/usr/bin/env python3
"""Qdrant client utilities for AI Beast.

Provides reusable client management and collection operations.
"""
import os


def get_qdrant_url() -> str:
    """Get Qdrant URL from environment or default."""
    port = os.environ.get("PORT_QDRANT", "6333")
    host = os.environ.get("AI_BEAST_BIND_ADDR", "127.0.0.1")
    return f"http://{host}:{port}"


def get_default_model() -> str:
    """Get default embedding model from environment or default."""
    return os.environ.get(
        "QDRANT_EMBED_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def get_default_collection() -> str:
    """Get default collection name from environment or default."""
    return os.environ.get("QDRANT_COLLECTION", "ai_beast")


class QdrantManager:
    """Manager class for Qdrant operations.

    Provides a higher-level interface for common Qdrant operations
    with connection pooling and sensible defaults.
    """

    def __init__(
        self,
        url: str | None = None,
        collection: str | None = None,
        model: str | None = None,
    ):
        """Initialize the Qdrant manager.

        Args:
            url: Qdrant server URL (default: from env or localhost:6333)
            collection: Default collection name
            model: Default embedding model
        """
        self.url = url or get_qdrant_url()
        self.collection = collection or get_default_collection()
        self.model = model or get_default_model()
        self._client = None
        self._embedder = None

    @property
    def client(self):
        """Lazy-loaded Qdrant client."""
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self.url)
        return self._client

    @property
    def embedder(self):
        """Lazy-loaded embedding model."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.model)
        return self._embedder

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """Embed text(s) using the configured model."""
        if isinstance(texts, str):
            texts = [texts]
        vectors = self.embedder.encode(
            texts, show_progress_bar=False, convert_to_numpy=True
        )
        return [v.tolist() for v in vectors]

    def is_healthy(self) -> bool:
        """Check if Qdrant server is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """List all collection names."""
        collections = self.client.get_collections()
        return [c.name for c in collections.collections]

    def collection_exists(self, name: str | None = None) -> bool:
        """Check if a collection exists."""
        name = name or self.collection
        return name in self.list_collections()

    def create_collection(
        self,
        name: str | None = None,
        vector_size: int | None = None,
        distance: str = "Cosine",
    ) -> bool:
        """Create a collection if it doesn't exist.

        Returns:
            True if collection was created, False if it existed
        """
        from qdrant_client.http.models import Distance, VectorParams

        name = name or self.collection
        if self.collection_exists(name):
            return False

        # Determine vector size from model if not specified
        if vector_size is None:
            vector_size = self.embedder.get_sentence_embedding_dimension()

        dist = getattr(Distance, distance.upper(), Distance.COSINE)
        self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=dist),
        )
        return True

    def delete_collection(self, name: str | None = None) -> bool:
        """Delete a collection.

        Returns:
            True if deleted, False if it didn't exist
        """
        name = name or self.collection
        if not self.collection_exists(name):
            return False
        self.client.delete_collection(name)
        return True

    def count(self, collection: str | None = None) -> int:
        """Get the number of points in a collection."""
        collection = collection or self.collection
        try:
            info = self.client.get_collection(collection)
            return info.points_count or 0
        except Exception:
            return 0

    def search(
        self,
        query: str,
        limit: int = 5,
        collection: str | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """Search for similar documents.

        Returns:
            List of result dicts with id, score, and payload
        """
        collection = collection or self.collection
        query_vector = self.embed(query)[0]

        search_params = {
            "collection_name": collection,
            "query_vector": query_vector,
            "limit": limit,
        }
        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold

        results = self.client.search(**search_params)

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "path": hit.payload.get("path", ""),
                "payload": hit.payload,
            }
            for hit in results
        ]

    def add_text(
        self,
        text: str,
        metadata: dict | None = None,
        collection: str | None = None,
        point_id: int | None = None,
    ) -> int:
        """Add a single text to the collection.

        Returns:
            The point ID used
        """
        import hashlib

        collection = collection or self.collection
        self.create_collection(collection)

        vector = self.embed(text)[0]

        if point_id is None:
            point_id = int(hashlib.md5(text.encode()).hexdigest()[:15], 16)

        payload = {"text": text}
        if metadata:
            payload.update(metadata)

        self.client.upsert(
            collection_name=collection,
            points=[{"id": point_id, "vector": vector, "payload": payload}],
        )

        return point_id

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        collection: str | None = None,
    ) -> list[int]:
        """Add multiple texts to the collection.

        Returns:
            List of point IDs used
        """
        import hashlib

        collection = collection or self.collection
        self.create_collection(collection)

        vectors = self.embed(texts)
        metadatas = metadatas or [{}] * len(texts)

        points = []
        ids = []
        for i, (text, vector, meta) in enumerate(
            zip(texts, vectors, metadatas, strict=True)
        ):
            point_id = int(hashlib.md5(f"{text}:{i}".encode()).hexdigest()[:15], 16)
            ids.append(point_id)
            payload = {"text": text}
            payload.update(meta)
            points.append({"id": point_id, "vector": vector, "payload": payload})

        # Batch upsert
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(collection_name=collection, points=batch)

        return ids

    def delete_by_path(
        self,
        path: str,
        collection: str | None = None,
    ) -> int:
        """Delete all points from a specific file path.

        Returns:
            Number of points deleted
        """
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue

        collection = collection or self.collection

        # Count first
        filter_cond = Filter(
            must=[FieldCondition(key="path", match=MatchValue(value=path))]
        )

        result = self.client.scroll(
            collection_name=collection,
            scroll_filter=filter_cond,
            limit=10000,
        )
        count = len(result[0])

        if count > 0:
            self.client.delete(
                collection_name=collection,
                points_selector=filter_cond,
            )

        return count


# Convenience function for quick access
def quick_search(
    query: str,
    collection: str = "ai_beast",
    limit: int = 5,
) -> list[dict]:
    """Quick search without instantiating manager."""
    manager = QdrantManager(collection=collection)
    return manager.search(query, limit=limit)


def quick_add(text: str, metadata: dict | None = None) -> int:
    """Quick add text without instantiating manager."""
    manager = QdrantManager()
    return manager.add_text(text, metadata)
