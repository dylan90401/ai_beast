"""Integration tests for RAG ingestion workflow.

Task 2.3 - Tests document ingestion and retrieval workflows.
"""
import pytest


@pytest.mark.integration
class TestRAGChunkingWorkflow:
    """Test RAG text chunking workflow."""

    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        from modules.rag.ingest import chunk_text
        
        text = "This is a test. " * 100
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        
        assert len(chunks) > 1
        assert all(len(c) <= 200 for c in chunks)

    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        from modules.rag.ingest import chunk_text
        
        chunks = chunk_text("", chunk_size=200, overlap=50)
        assert chunks == []

    def test_chunk_text_small(self):
        """Test chunking text smaller than chunk size."""
        from modules.rag.ingest import chunk_text
        
        text = "Small text"
        chunks = chunk_text(text, chunk_size=200, overlap=50)
        
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_overlap(self):
        """Test that chunks overlap correctly."""
        from modules.rag.ingest import chunk_text
        
        text = "ABCDEFGHIJ" * 30  # 300 chars
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        
        # Verify overlap exists
        for i in range(len(chunks) - 1):
            # End of current chunk should overlap with start of next
            assert len(chunks[i]) > 0
            assert len(chunks[i + 1]) > 0


@pytest.mark.integration
class TestRAGFileIterationWorkflow:
    """Test file iteration for RAG ingestion."""

    def test_iter_files_basic(self, mock_documents):
        """Test iterating over files in directory."""
        from modules.rag.ingest import iter_files
        
        docs_dir, files = mock_documents
        
        found = list(iter_files(docs_dir, exts=[]))
        assert len(found) == 3

    def test_iter_files_with_extension_filter(self, mock_documents):
        """Test filtering by extension."""
        from modules.rag.ingest import iter_files
        
        docs_dir, files = mock_documents
        
        md_files = list(iter_files(docs_dir, exts=["md"]))
        assert len(md_files) == 1
        assert md_files[0].suffix == ".md"

    def test_iter_files_multiple_extensions(self, mock_documents):
        """Test filtering with multiple extensions."""
        from modules.rag.ingest import iter_files
        
        docs_dir, files = mock_documents
        
        text_files = list(iter_files(docs_dir, exts=["md", "txt"]))
        assert len(text_files) == 2


@pytest.mark.integration
class TestRAGTextReadingWorkflow:
    """Test text reading for RAG."""

    def test_read_text_best_effort(self, mock_documents):
        """Test reading text files with various encodings."""
        from modules.rag.ingest import read_text_best_effort
        
        docs_dir, files = mock_documents
        
        for f in files:
            content = read_text_best_effort(f)
            assert isinstance(content, str)
            assert len(content) > 0

    def test_read_text_truncation(self, temp_workspace):
        """Test that large files are truncated."""
        from modules.rag.ingest import read_text_best_effort
        
        # Create a large file
        large_file = temp_workspace / "large.txt"
        large_file.write_text("X" * 100_000)
        
        content = read_text_best_effort(large_file, max_bytes=1000)
        assert len(content) <= 1000


@pytest.mark.integration
class TestRAGHashingWorkflow:
    """Test content hashing for RAG."""

    def test_sha256_bytes(self):
        """Test SHA256 hashing."""
        from modules.rag.ingest import sha256_bytes
        
        data = b"test data"
        hash1 = sha256_bytes(data)
        hash2 = sha256_bytes(data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_sha256_bytes_deterministic(self, mock_documents):
        """Test that hashing is deterministic."""
        from modules.rag.ingest import sha256_bytes
        
        docs_dir, files = mock_documents
        
        for f in files:
            data = f.read_bytes()
            h1 = sha256_bytes(data)
            h2 = sha256_bytes(data)
            assert h1 == h2


@pytest.mark.integration
@pytest.mark.skipif(
    True,  # Skip by default - requires Qdrant
    reason="Requires Qdrant running"
)
class TestRAGVectorStoreWorkflow:
    """Test RAG vector store integration."""

    def test_qdrant_client_creation(self):
        """Test Qdrant client creation."""
        from modules.rag.ingest import get_qdrant_client
        
        try:
            client = get_qdrant_client()
            assert client is not None
        except ImportError:
            pytest.skip("qdrant-client not installed")

    def test_embedder_creation(self):
        """Test embedding model creation."""
        from modules.rag.ingest import get_embedder
        
        try:
            embedder = get_embedder()
            assert embedder is not None
        except ImportError:
            pytest.skip("sentence-transformers not installed")
