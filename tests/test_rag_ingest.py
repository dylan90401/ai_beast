from pathlib import Path

from modules.rag.ingest import chunk_text, read_text_best_effort


def test_chunk_text_overlap():
    text = "a" * 50
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    assert chunks
    assert all(len(c) <= 20 for c in chunks)


def test_read_text_best_effort(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")
    out = read_text_best_effort(path)
    assert out == "hello"
