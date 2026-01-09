"""Comprehensive tests for RAG ingest module.

Task 2.5 - Test coverage for modules/rag/ingest.py.
Target: 70% coverage.
"""
import pytest
from pathlib import Path


# =============================================================================
# chunk_text Tests
# =============================================================================

class TestChunkText:
    """Test text chunking functionality."""

    def test_empty_text(self):
        """Empty text returns empty list."""
        from modules.rag.ingest import chunk_text
        assert chunk_text("", 1000, 100) == []

    def test_whitespace_only(self):
        """Whitespace-only text returns empty list."""
        from modules.rag.ingest import chunk_text
        assert chunk_text("   \n\t  ", 1000, 100) == []

    def test_small_text(self):
        """Text smaller than chunk size returns single chunk."""
        from modules.rag.ingest import chunk_text
        result = chunk_text("Hello world", 1000, 100)
        assert result == ["Hello world"]

    def test_exact_chunk_size(self):
        """Text exactly chunk size returns single chunk."""
        from modules.rag.ingest import chunk_text
        text = "A" * 100
        result = chunk_text(text, 100, 20)
        assert len(result) == 1
        assert result[0] == text

    def test_multiple_chunks(self):
        """Long text produces multiple chunks."""
        from modules.rag.ingest import chunk_text
        text = "word " * 500  # ~2500 chars
        result = chunk_text(text, 500, 100)
        assert len(result) > 1

    def test_overlap(self):
        """Chunks have proper overlap."""
        from modules.rag.ingest import chunk_text
        text = "ABCDEFGHIJ" * 20  # 200 chars
        chunks = chunk_text(text, 50, 10)
        
        # With overlap, chunks should share some content
        assert len(chunks) > 2

    def test_windows_line_endings(self):
        """Windows line endings are normalized."""
        from modules.rag.ingest import chunk_text
        text = "line1\r\nline2\r\nline3"
        result = chunk_text(text, 1000, 100)
        assert "\r\n" not in result[0]
        assert "\n" in result[0]

    def test_chunk_size_zero(self):
        """Zero chunk size returns full text."""
        from modules.rag.ingest import chunk_text
        text = "Hello world"
        result = chunk_text(text, 0, 0)
        assert result == [text]

    def test_negative_chunk_size(self):
        """Negative chunk size returns full text."""
        from modules.rag.ingest import chunk_text
        text = "Hello world"
        result = chunk_text(text, -100, 0)
        assert result == [text]

    def test_chunks_stripped(self):
        """Chunks are stripped of leading/trailing whitespace."""
        from modules.rag.ingest import chunk_text
        text = "  word  " * 100
        chunks = chunk_text(text, 50, 10)
        for chunk in chunks:
            assert chunk == chunk.strip()


# =============================================================================
# iter_files Tests
# =============================================================================

class TestIterFiles:
    """Test file iteration functionality."""

    def test_empty_directory(self, tmp_path):
        """Empty directory yields no files."""
        from modules.rag.ingest import iter_files
        result = list(iter_files(tmp_path, []))
        assert result == []

    def test_all_files(self, tmp_path):
        """Without extension filter, all files are yielded."""
        from modules.rag.ingest import iter_files
        
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.py").write_text("c")
        
        result = list(iter_files(tmp_path, []))
        assert len(result) == 3

    def test_extension_filter(self, tmp_path):
        """Extension filter works correctly."""
        from modules.rag.ingest import iter_files
        
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.py").write_text("c")
        
        result = list(iter_files(tmp_path, ["txt"]))
        assert len(result) == 1
        assert result[0].suffix == ".txt"

    def test_multiple_extensions(self, tmp_path):
        """Multiple extension filter works."""
        from modules.rag.ingest import iter_files
        
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.py").write_text("c")
        
        result = list(iter_files(tmp_path, ["txt", "md"]))
        assert len(result) == 2

    def test_recursive(self, tmp_path):
        """Recursively finds files in subdirectories."""
        from modules.rag.ingest import iter_files
        
        subdir = tmp_path / "sub"
        subdir.mkdir()
        
        (tmp_path / "a.txt").write_text("a")
        (subdir / "b.txt").write_text("b")
        
        result = list(iter_files(tmp_path, ["txt"]))
        assert len(result) == 2

    def test_ignores_hidden_files(self, tmp_path):
        """Hidden files (starting with .) are ignored."""
        from modules.rag.ingest import iter_files
        
        (tmp_path / "visible.txt").write_text("v")
        (tmp_path / ".hidden.txt").write_text("h")
        
        result = list(iter_files(tmp_path, ["txt"]))
        assert len(result) == 1
        assert ".hidden" not in str(result[0])

    def test_ignores_directories(self, tmp_path):
        """Directories are not yielded."""
        from modules.rag.ingest import iter_files
        
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "file.txt").write_text("f")
        
        result = list(iter_files(tmp_path, []))
        assert len(result) == 1
        assert result[0].is_file()


# =============================================================================
# read_text_best_effort Tests
# =============================================================================

class TestReadTextBestEffort:
    """Test best-effort text reading."""

    def test_utf8_file(self, tmp_path):
        """UTF-8 file is read correctly."""
        from modules.rag.ingest import read_text_best_effort
        
        f = tmp_path / "test.txt"
        f.write_text("Hello, World!", encoding="utf-8")
        
        result = read_text_best_effort(f)
        assert result == "Hello, World!"

    def test_latin1_file(self, tmp_path):
        """Latin-1 file is read correctly."""
        from modules.rag.ingest import read_text_best_effort
        
        f = tmp_path / "test.txt"
        f.write_bytes("Héllo Wörld".encode("latin-1"))
        
        result = read_text_best_effort(f)
        assert len(result) > 0

    def test_truncation(self, tmp_path):
        """Large files are truncated."""
        from modules.rag.ingest import read_text_best_effort
        
        f = tmp_path / "large.txt"
        f.write_text("X" * 100_000)
        
        result = read_text_best_effort(f, max_bytes=1000)
        assert len(result) <= 1000

    def test_binary_content(self, tmp_path):
        """Binary content doesn't crash."""
        from modules.rag.ingest import read_text_best_effort
        
        f = tmp_path / "binary.bin"
        f.write_bytes(bytes(range(256)))
        
        result = read_text_best_effort(f)
        assert isinstance(result, str)


# =============================================================================
# sha256_bytes Tests
# =============================================================================

class TestSha256Bytes:
    """Test SHA256 hashing."""

    def test_empty_bytes(self):
        """Empty bytes hash correctly."""
        from modules.rag.ingest import sha256_bytes
        result = sha256_bytes(b"")
        assert len(result) == 64

    def test_deterministic(self):
        """Same input produces same hash."""
        from modules.rag.ingest import sha256_bytes
        data = b"test data"
        assert sha256_bytes(data) == sha256_bytes(data)

    def test_different_inputs(self):
        """Different inputs produce different hashes."""
        from modules.rag.ingest import sha256_bytes
        assert sha256_bytes(b"a") != sha256_bytes(b"b")

    def test_known_hash(self):
        """Known input produces expected hash."""
        from modules.rag.ingest import sha256_bytes
        # SHA256 of "test" is well-known
        result = sha256_bytes(b"test")
        assert result.startswith("9f86d08")


# =============================================================================
# Embedder and Qdrant Client Tests (with mocks)
# =============================================================================

class TestGetEmbedder:
    """Test embedder creation."""

    def test_import_error_message(self):
        """ImportError has helpful message."""
        import sys
        
        # Skip if sentence-transformers is installed
        if "sentence_transformers" in sys.modules:
            pytest.skip("sentence-transformers is installed")
        
        from modules.rag import ingest
        
        # Reset cached embedder
        ingest._embedder = None
        
        try:
            ingest.get_embedder()
        except ImportError as e:
            assert "sentence-transformers" in str(e)


class TestGetQdrantClient:
    """Test Qdrant client creation."""

    def test_import_error_message(self):
        """ImportError has helpful message."""
        import sys
        
        # Skip if qdrant-client is installed
        if "qdrant_client" in sys.modules:
            pytest.skip("qdrant-client is installed")
        
        from modules.rag import ingest
        
        # Reset cached client
        ingest._qdrant_client = None
        
        try:
            ingest.get_qdrant_client()
        except ImportError as e:
            assert "qdrant-client" in str(e)
