"""RAG (Retrieval-Augmented Generation) module for AI Beast.

This module provides document ingestion, chunking, embedding, and retrieval
functionality for building RAG pipelines with Qdrant vector store.
"""

from .client import (
    QdrantManager,
    get_default_collection,
    get_default_model,
    get_qdrant_url,
    quick_add,
    quick_search,
)
from .ingest import (
    chunk_text,
    embed_text,
    ingest_directory,
    ingest_file,
    iter_files,
    read_text_best_effort,
)
from .parallel_ingest import (
    BatchStats,
    IngestionResult,
    IngestionStatus,
    IngestionTask,
    ParallelIngestor,
    parallel_ingest_directory,
    parallel_ingest_directory_sync,
)
from .query import (
    collection_info,
    delete_collection,
    get_context,
    list_collections,
    search,
)

__all__ = [
    # Ingest functions
    "chunk_text",
    "embed_text",
    "ingest_file",
    "ingest_directory",
    "read_text_best_effort",
    "iter_files",
    # Parallel ingestion
    "ParallelIngestor",
    "IngestionTask",
    "IngestionResult",
    "IngestionStatus",
    "BatchStats",
    "parallel_ingest_directory",
    "parallel_ingest_directory_sync",
    # Query functions
    "search",
    "get_context",
    "list_collections",
    "collection_info",
    "delete_collection",
    # Client utilities
    "QdrantManager",
    "get_qdrant_url",
    "get_default_model",
    "get_default_collection",
    "quick_search",
    "quick_add",
]

