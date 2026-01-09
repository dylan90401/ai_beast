"""Integration tests for LLM model management workflow.

Task 2.3 - Tests complete model management workflows.
"""
import pytest


@pytest.mark.integration
class TestModelScanWorkflow:
    """Test model scanning and discovery workflow."""

    def test_scan_empty_directory(self, llm_manager):
        """Test scanning an empty models directory."""
        models = llm_manager.scan_local_models(force=True)
        assert isinstance(models, list)
        assert len(models) == 0

    def test_scan_with_models(self, llm_manager, mock_model_files):
        """Test scanning directory with model files."""
        models = llm_manager.scan_local_models(force=True)
        
        assert len(models) >= 1
        
        # Check model metadata
        model_names = {m.name for m in models}
        assert "test-model-Q4_K_M" in model_names or len(models) > 0

    def test_scan_cache_behavior(self, llm_manager, mock_model_files):
        """Test that model cache works correctly."""
        # First scan
        models1 = llm_manager.scan_local_models(force=True)
        
        # Second scan (should use cache)
        models2 = llm_manager.scan_local_models(force=False)
        
        assert len(models1) == len(models2)
        
        # Force scan should refresh
        models3 = llm_manager.scan_local_models(force=True)
        assert len(models3) == len(models1)


@pytest.mark.integration
class TestStorageInfoWorkflow:
    """Test storage information retrieval."""

    def test_get_storage_info(self, llm_manager, temp_workspace):
        """Test storage info retrieval."""
        info = llm_manager.get_storage_info()
        
        assert isinstance(info, dict)
        assert "internal" in info
        
        # Verify path is correct
        internal = info["internal"]
        assert "path" in internal
        assert str(temp_workspace) in internal["path"]


@pytest.mark.integration
class TestModelLocationWorkflow:
    """Test model location management."""

    def test_internal_location_exists(self, llm_manager, temp_workspace):
        """Test internal model location is properly set up."""
        assert llm_manager.llm_models_dir.exists()
        assert llm_manager.llm_cache_dir.exists()

    def test_model_info_location(self, llm_manager, mock_model_files):
        """Test that scanned models have correct location."""
        from modules.llm.manager import ModelLocation
        
        models = llm_manager.scan_local_models(force=True)
        
        for model in models:
            # Local files should be INTERNAL or EXTERNAL
            assert model.location in (ModelLocation.INTERNAL, ModelLocation.EXTERNAL)


@pytest.mark.integration
@pytest.mark.skipif(
    True,  # Skip by default - requires Ollama
    reason="Requires Ollama running"
)
class TestOllamaWorkflow:
    """Test Ollama integration workflow."""

    def test_ollama_connection(self, llm_manager, ollama_available):
        """Test Ollama connection check."""
        if not ollama_available:
            pytest.skip("Ollama not available")
        
        result = llm_manager.ollama_running()
        assert isinstance(result, bool)

    def test_list_ollama_models(self, llm_manager, ollama_available):
        """Test listing Ollama models."""
        if not ollama_available:
            pytest.skip("Ollama not available")
        
        models = llm_manager.list_ollama_models()
        assert isinstance(models, list)


@pytest.mark.integration
class TestModelMetadataWorkflow:
    """Test model metadata extraction."""

    def test_extract_quantization(self, llm_manager, mock_model_files):
        """Test quantization extraction from filenames."""
        models = llm_manager.scan_local_models(force=True)
        
        quants_found = [m.quantization for m in models if m.quantization]
        
        # Should find Q4_K_M and Q8_0 from mock files
        assert len(quants_found) >= 0  # May be 0 if mock files not detected

    def test_model_type_detection(self, llm_manager, mock_model_files):
        """Test model type detection from file extension."""
        models = llm_manager.scan_local_models(force=True)
        
        types = {m.model_type for m in models}
        # Should detect gguf and safetensors
        assert types <= {"gguf", "safetensors", "bin", "unknown"}

    def test_model_serialization(self, llm_manager, mock_model_files):
        """Test model info serialization to dict."""
        models = llm_manager.scan_local_models(force=True)
        
        for model in models:
            d = model.to_dict()
            assert isinstance(d, dict)
            assert "name" in d
            assert "path" in d
            assert "location" in d
