"""Property-based tests for LLM Manager using Hypothesis.

Task 2.2 - Enhanced property-based testing coverage.
"""
from hypothesis import given, strategies as st, settings, assume
import pytest

from modules.llm import manager


# =============================================================================
# URL Validation Property Tests
# =============================================================================

@given(st.text(min_size=1))
def test_safe_filename_rejects_separators(text):
    """Property: Filenames with path separators are always rejected."""
    if "/" in text or "\\" in text:
        assert manager._safe_filename(text) == ""


@given(st.text(min_size=1))
def test_validate_download_url_requires_http(text):
    """Property: Only http/https schemes are valid."""
    raw = f"{text}://example.com/model.gguf"
    ok, _ = manager._validate_download_url(raw)
    assert ok is (text in ("http", "https"))


@given(st.text(min_size=0, max_size=100))
def test_safe_filename_never_crashes(text):
    """Property: _safe_filename never raises exceptions."""
    result = manager._safe_filename(text)
    assert isinstance(result, str)


@given(st.text(min_size=0, max_size=500))
def test_validate_url_never_crashes(text):
    """Property: URL validation never raises exceptions."""
    ok, msg = manager._validate_download_url(text)
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


@given(st.text(min_size=1, max_size=100).filter(lambda x: "/" not in x and "\\" not in x and x not in (".", "..")))
def test_safe_filename_preserves_valid_names(text):
    """Property: Valid filenames are preserved."""
    # Filter out null bytes
    assume("\x00" not in text)
    result = manager._safe_filename(text)
    # Either empty (rejected) or same as input
    assert result == "" or result == text


# =============================================================================
# Human Size Property Tests
# =============================================================================

@given(st.integers(min_value=0, max_value=10**18))
def test_human_size_always_returns_string(size):
    """Property: _human_size always returns a valid string."""
    result = manager._human_size(size)
    assert isinstance(result, str)
    assert len(result) > 0


@given(st.integers(min_value=0, max_value=10**18))
def test_human_size_contains_unit(size):
    """Property: Result always contains a size unit."""
    result = manager._human_size(size)
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    assert any(unit in result for unit in units)


@given(st.integers(min_value=0, max_value=10**18))
def test_human_size_contains_number(size):
    """Property: Result always contains numeric value."""
    result = manager._human_size(size)
    assert any(char.isdigit() for char in result)


# =============================================================================
# Quantization Extraction Property Tests
# =============================================================================

@given(st.text(min_size=0, max_size=200))
def test_extract_quant_never_crashes(filename):
    """Property: _extract_quant never raises exceptions."""
    result = manager._extract_quant(filename)
    assert isinstance(result, str)


@given(st.text(min_size=0, max_size=200))
def test_extract_quant_result_uppercase(filename):
    """Property: If quantization found, it's uppercase."""
    result = manager._extract_quant(filename)
    if result:
        assert result.isupper()


@given(st.sampled_from(["Q4_K_M", "Q8_0", "Q5_K_S", "Q6_K", "fp16", "FP32"]))
def test_extract_quant_finds_known_patterns(quant):
    """Property: Known quantization patterns are detected."""
    filename = f"model-{quant}.gguf"
    result = manager._extract_quant(filename)
    assert result == quant.upper()


# =============================================================================
# Path Resolution Property Tests
# =============================================================================

@given(st.text(min_size=1, max_size=50).filter(lambda x: "/" not in x and "\\" not in x))
@settings(max_examples=50)
def test_resolve_dest_safe_filenames(filename, tmp_path):
    """Property: Safe filenames resolve within destination."""
    assume("\x00" not in filename)
    assume(filename not in (".", ".."))
    
    ok, result = manager._resolve_dest(tmp_path, filename)
    if ok:
        from pathlib import Path
        assert isinstance(result, Path)
        # Verify path is within tmp_path
        assert str(result).startswith(str(tmp_path))


@given(st.text(min_size=1, max_size=50))
@settings(max_examples=50)
def test_resolve_dest_rejects_traversal(filename, tmp_path):
    """Property: Path traversal attempts are rejected."""
    if ".." in filename:
        ok, result = manager._resolve_dest(tmp_path, filename)
        # Should either fail or stay within directory
        if ok:
            from pathlib import Path
            assert isinstance(result, Path)
            assert str(result).startswith(str(tmp_path))


# =============================================================================
# ModelInfo Property Tests
# =============================================================================

@given(
    name=st.text(min_size=1, max_size=100),
    size=st.integers(min_value=0, max_value=10**15)
)
def test_model_info_serialization(name, size):
    """Property: ModelInfo serializes to valid dict."""
    from modules.llm.manager import ModelInfo, ModelLocation
    
    info = ModelInfo(
        name=name,
        path="/test/path",
        size_bytes=size,
        location=ModelLocation.INTERNAL
    )
    d = info.to_dict()
    
    assert isinstance(d, dict)
    assert d["name"] == name
    assert d["size_bytes"] == size
    assert d["location"] == "internal"
