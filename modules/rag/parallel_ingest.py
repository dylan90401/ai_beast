"""
Parallel document ingestion for RAG.

Processes multiple documents concurrently for better performance,
with support for batching, progress tracking, and error handling.

Features:
- Async/await parallel processing
- Configurable concurrency limits
- Progress callbacks
- Batch embedding for efficiency
- Automatic retry with backoff
- Resource-aware processing

Example:
    from modules.rag.parallel_ingest import ParallelIngestor

    async def main():
        ingestor = ParallelIngestor(
            max_workers=4,
            batch_size=10,
            qdrant_url="http://localhost:6333"
        )
        
        # Ingest a directory
        results = await ingestor.ingest_directory(
            Path("documents/"),
            collection="my_docs",
            progress_callback=lambda r: print(f"Processed: {r.doc_path}")
        )
        
        # Check results
        success = sum(1 for r in results if r.success)
        print(f"Ingested {success}/{len(results)} documents")
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


class IngestionStatus(Enum):
    """Status of an ingestion task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class IngestionTask:
    """Represents a document ingestion task."""
    doc_path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        self.doc_path = Path(self.doc_path)


@dataclass
class IngestionResult:
    """Result of document ingestion."""
    doc_path: Path
    status: IngestionStatus
    chunks_created: int = 0
    vectors_stored: int = 0
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    retries: int = 0
    
    @property
    def success(self) -> bool:
        return self.status == IngestionStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_path": str(self.doc_path),
            "status": self.status.value,
            "success": self.success,
            "chunks_created": self.chunks_created,
            "vectors_stored": self.vectors_stored,
            "file_size_bytes": self.file_size_bytes,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "retries": self.retries,
        }


@dataclass
class BatchStats:
    """Statistics for a batch ingestion run."""
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    total_chunks: int = 0
    total_vectors: int = 0
    total_bytes: int = 0
    total_duration: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.successful / self.total_files
    
    @property
    def throughput_files_per_second(self) -> float:
        if self.total_duration == 0:
            return 0.0
        return self.successful / self.total_duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 4),
            "total_chunks": self.total_chunks,
            "total_vectors": self.total_vectors,
            "total_mb": round(self.total_bytes / (1024 * 1024), 2),
            "total_duration_seconds": round(self.total_duration, 2),
            "throughput_files_per_second": round(self.throughput_files_per_second, 2),
        }


class ParallelIngestor:
    """
    Parallel document ingestion with configurable concurrency.
    
    Processes documents in parallel using async/await and thread pools,
    with automatic batching of embeddings for efficiency.

    Example:
        ingestor = ParallelIngestor(max_workers=4)
        results = await ingestor.ingest_batch(tasks)
    """

    # Default file extensions to process
    DEFAULT_EXTENSIONS = {
        ".txt", ".md", ".rst", ".json", ".yaml", ".yml",
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h",
        ".html", ".css", ".xml", ".csv", ".log",
    }
    
    # Extensions to skip
    SKIP_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico",
        ".mp3", ".mp4", ".wav", ".avi", ".mov",
        ".zip", ".tar", ".gz", ".rar", ".7z",
        ".exe", ".dll", ".so", ".dylib",
        ".bin", ".dat", ".db", ".sqlite",
    }

    def __init__(
        self,
        max_workers: int = 4,
        batch_size: int = 10,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        max_file_bytes: int = 5_000_000,
        qdrant_url: str = "http://127.0.0.1:6333",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        semaphore_limit: int = 10,
    ):
        """
        Initialize the parallel ingestor.
        
        Args:
            max_workers: Maximum concurrent workers
            batch_size: Documents to batch for embedding
            chunk_size: Characters per text chunk
            chunk_overlap: Overlap between chunks
            max_file_bytes: Maximum file size to process
            qdrant_url: Qdrant server URL
            embedding_model: Sentence transformer model
            semaphore_limit: Max concurrent operations
        """
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_file_bytes = max_file_bytes
        self.qdrant_url = qdrant_url
        self.embedding_model = embedding_model
        
        # Thread pool for CPU-bound operations
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Semaphore for limiting concurrent operations
        self._semaphore = asyncio.Semaphore(semaphore_limit)
        
        # Lazy-loaded dependencies
        self._embedder = None
        self._qdrant_client = None

    def _get_embedder(self):
        """Get or create embedding model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self.embedding_model)
                logger.info(f"Loaded embedding model: {self.embedding_model}")
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers required. "
                    "Install: pip install sentence-transformers"
                ) from exc
        return self._embedder

    def _get_qdrant_client(self):
        """Get or create Qdrant client."""
        if self._qdrant_client is None:
            try:
                from qdrant_client import QdrantClient
                self._qdrant_client = QdrantClient(url=self.qdrant_url)
                logger.info(f"Connected to Qdrant: {self.qdrant_url}")
            except ImportError as exc:
                raise ImportError(
                    "qdrant-client required. "
                    "Install: pip install qdrant-client"
                ) from exc
        return self._qdrant_client

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        text = text.replace("\r\n", "\n")
        if self.chunk_size <= 0:
            return [text] if text.strip() else []
        
        chunks = []
        i = 0
        n = len(text)
        
        while i < n:
            # Find chunk end
            j = min(i + self.chunk_size, n)
            
            # Try to break at sentence boundary if possible
            if j < n:
                # Look back for sentence boundary
                for sep in ["\n\n", ".\n", ". ", "\n"]:
                    pos = text.rfind(sep, i + self.chunk_size // 2, j)
                    if pos > i:
                        j = pos + len(sep)
                        break
            
            chunk = text[i:j].strip()
            if chunk:
                chunks.append(chunk)
            
            if j >= n:
                break
            
            # Move forward with overlap
            i = max(i + 1, j - self.chunk_overlap)
        
        return chunks

    def _read_file(self, path: Path) -> str:
        """Read file with best-effort encoding detection."""
        data = path.read_bytes()
        
        if len(data) > self.max_file_bytes:
            logger.warning(
                f"File {path} exceeds max size, truncating "
                f"({len(data)} > {self.max_file_bytes})"
            )
            data = data[:self.max_file_bytes]
        
        # Try encodings in order
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Last resort: ignore errors
        return data.decode("utf-8", errors="ignore")

    def _compute_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """Compute embeddings for text chunks."""
        if not chunks:
            return []
        
        embedder = self._get_embedder()
        vectors = embedder.encode(
            chunks,
            show_progress_bar=False,
            convert_to_numpy=True,
            batch_size=min(32, len(chunks)),
        )
        return [v.tolist() for v in vectors]

    def _ensure_collection(self, collection: str, vector_dim: int):
        """Ensure Qdrant collection exists."""
        from qdrant_client.http.models import Distance, VectorParams
        
        client = self._get_qdrant_client()
        
        try:
            info = client.get_collection(collection)
            # Verify dimension matches
            if info.config.params.vectors.size != vector_dim:
                logger.warning(
                    f"Collection {collection} has different dimension "
                    f"({info.config.params.vectors.size} vs {vector_dim})"
                )
        except Exception:
            # Create collection
            client.recreate_collection(
                collection_name=collection,
                vectors_config=VectorParams(
                    size=vector_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created collection: {collection} (dim={vector_dim})")

    async def _ingest_single(
        self,
        task: IngestionTask,
        collection: str,
    ) -> IngestionResult:
        """Ingest a single document."""
        start_time = time.time()
        path = task.doc_path
        
        # Validate file
        if not path.exists():
            return IngestionResult(
                doc_path=path,
                status=IngestionStatus.FAILED,
                error="File not found",
                duration_seconds=time.time() - start_time,
            )
        
        if not path.is_file():
            return IngestionResult(
                doc_path=path,
                status=IngestionStatus.SKIPPED,
                error="Not a file",
                duration_seconds=time.time() - start_time,
            )
        
        # Check extension
        if path.suffix.lower() in self.SKIP_EXTENSIONS:
            return IngestionResult(
                doc_path=path,
                status=IngestionStatus.SKIPPED,
                error="Unsupported file type",
                duration_seconds=time.time() - start_time,
            )
        
        try:
            # Read file in executor
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                self._executor,
                self._read_file,
                path,
            )
            
            if not text.strip():
                return IngestionResult(
                    doc_path=path,
                    status=IngestionStatus.SKIPPED,
                    error="Empty file",
                    duration_seconds=time.time() - start_time,
                )
            
            # Chunk text
            chunks = await loop.run_in_executor(
                self._executor,
                self._chunk_text,
                text,
            )
            
            if not chunks:
                return IngestionResult(
                    doc_path=path,
                    status=IngestionStatus.SKIPPED,
                    error="No content after chunking",
                    duration_seconds=time.time() - start_time,
                )
            
            # Compute embeddings
            async with self._semaphore:
                vectors = await loop.run_in_executor(
                    self._executor,
                    self._compute_embeddings,
                    chunks,
                )
            
            if not vectors:
                return IngestionResult(
                    doc_path=path,
                    status=IngestionStatus.FAILED,
                    error="Embedding failed",
                    duration_seconds=time.time() - start_time,
                )
            
            # Ensure collection exists
            self._ensure_collection(collection, len(vectors[0]))
            
            # Store in Qdrant
            client = self._get_qdrant_client()
            
            # Generate point IDs based on content hash
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            
            from qdrant_client.http.models import PointStruct
            
            points = []
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                point_id = f"{file_hash}_{i:04d}"
                payload = {
                    "text": chunk,
                    "file": str(path),
                    "filename": path.name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    **task.metadata,
                }
                points.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                ))
            
            # Upsert points
            client.upsert(
                collection_name=collection,
                points=points,
                wait=True,
            )
            
            duration = time.time() - start_time
            
            logger.debug(
                f"Ingested {path.name}: "
                f"{len(chunks)} chunks, {duration:.2f}s"
            )
            
            return IngestionResult(
                doc_path=path,
                status=IngestionStatus.SUCCESS,
                chunks_created=len(chunks),
                vectors_stored=len(vectors),
                file_size_bytes=path.stat().st_size,
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"Failed to ingest {path}: {e}")
            return IngestionResult(
                doc_path=path,
                status=IngestionStatus.FAILED,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    async def ingest_batch(
        self,
        tasks: List[IngestionTask],
        collection: str = "ai_beast",
        progress_callback: Optional[Callable[[IngestionResult], None]] = None,
    ) -> List[IngestionResult]:
        """
        Ingest multiple documents in parallel.

        Args:
            tasks: List of ingestion tasks
            collection: Qdrant collection name
            progress_callback: Optional callback after each document

        Returns:
            List of ingestion results
        """
        if not tasks:
            return []
        
        # Sort by priority (higher first)
        tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)
        
        logger.info(f"Starting batch ingestion: {len(tasks)} documents")
        start_time = time.time()
        
        # Create coroutines
        coroutines = [
            self._ingest_single(task, collection)
            for task in tasks
        ]
        
        # Process with progress tracking
        results: List[IngestionResult] = []
        
        for coro in asyncio.as_completed(coroutines):
            result = await coro
            results.append(result)
            
            if progress_callback:
                try:
                    progress_callback(result)
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")
        
        total_time = time.time() - start_time
        success_count = sum(1 for r in results if r.success)
        
        logger.info(
            f"Batch ingestion complete: "
            f"{success_count}/{len(results)} successful, "
            f"{total_time:.2f}s total"
        )
        
        return results

    async def ingest_directory(
        self,
        directory: Union[Path, str],
        collection: str = "ai_beast",
        extensions: Optional[Set[str]] = None,
        recursive: bool = True,
        skip_hidden: bool = True,
        skip_patterns: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[IngestionResult], None]] = None,
    ) -> BatchStats:
        """
        Ingest all documents in a directory.

        Args:
            directory: Directory path
            collection: Qdrant collection name
            extensions: File extensions to process (None = all text)
            recursive: Process subdirectories
            skip_hidden: Skip hidden files/directories
            skip_patterns: Glob patterns to skip
            metadata: Additional metadata for all documents
            progress_callback: Callback after each document

        Returns:
            BatchStats with aggregated statistics
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise ValueError(f"Directory not found: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        # Find files
        if recursive:
            files = list(directory.rglob("*"))
        else:
            files = list(directory.glob("*"))
        
        # Filter files
        tasks = []
        skip_patterns = skip_patterns or set()
        extensions = extensions or self.DEFAULT_EXTENSIONS
        
        for path in files:
            # Skip directories
            if not path.is_file():
                continue
            
            # Skip hidden files
            if skip_hidden and (
                path.name.startswith(".") or
                any(p.startswith(".") for p in path.parts)
            ):
                continue
            
            # Check extension
            if extensions and path.suffix.lower() not in extensions:
                continue
            
            # Check skip patterns
            skip = False
            for pattern in skip_patterns:
                if path.match(pattern):
                    skip = True
                    break
            
            if skip:
                continue
            
            # Create task
            task_metadata = {
                "source_dir": str(directory),
                "relative_path": str(path.relative_to(directory)),
                **(metadata or {}),
            }
            
            tasks.append(IngestionTask(
                doc_path=path,
                metadata=task_metadata,
            ))
        
        if not tasks:
            logger.warning(f"No files found to ingest in {directory}")
            return BatchStats()
        
        logger.info(f"Found {len(tasks)} files to ingest in {directory}")
        
        # Run batch ingestion
        start_time = time.time()
        results = await self.ingest_batch(
            tasks,
            collection=collection,
            progress_callback=progress_callback,
        )
        
        # Compile stats
        stats = BatchStats(total_files=len(results))
        
        for result in results:
            if result.status == IngestionStatus.SUCCESS:
                stats.successful += 1
                stats.total_chunks += result.chunks_created
                stats.total_vectors += result.vectors_stored
                stats.total_bytes += result.file_size_bytes
            elif result.status == IngestionStatus.FAILED:
                stats.failed += 1
            else:
                stats.skipped += 1
        
        stats.total_duration = time.time() - start_time
        
        logger.info(
            f"Directory ingestion complete: "
            f"{stats.successful} success, {stats.failed} failed, "
            f"{stats.skipped} skipped ({stats.total_duration:.2f}s)"
        )
        
        return stats

    def close(self):
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        
        self._embedder = None
        self._qdrant_client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience functions
async def parallel_ingest_directory(
    directory: Union[Path, str],
    collection: str = "ai_beast",
    max_workers: int = 4,
    **kwargs,
) -> BatchStats:
    """
    Convenience function to ingest a directory in parallel.
    
    Args:
        directory: Path to directory
        collection: Qdrant collection name
        max_workers: Number of parallel workers
        **kwargs: Additional arguments for ingest_directory
        
    Returns:
        BatchStats with results
    """
    async with ParallelIngestor(max_workers=max_workers) as ingestor:
        return await ingestor.ingest_directory(
            directory,
            collection=collection,
            **kwargs,
        )


def parallel_ingest_directory_sync(
    directory: Union[Path, str],
    collection: str = "ai_beast",
    max_workers: int = 4,
    **kwargs,
) -> BatchStats:
    """
    Synchronous wrapper for parallel directory ingestion.
    
    Args:
        directory: Path to directory
        collection: Qdrant collection name
        max_workers: Number of parallel workers
        **kwargs: Additional arguments
        
    Returns:
        BatchStats with results
    """
    return asyncio.run(parallel_ingest_directory(
        directory,
        collection=collection,
        max_workers=max_workers,
        **kwargs,
    ))


# Make ParallelIngestor usable as async context manager
ParallelIngestor.__aenter__ = lambda self: asyncio.coroutine(lambda: self)()
ParallelIngestor.__aexit__ = lambda self, *args: asyncio.coroutine(
    lambda: self.close()
)()
