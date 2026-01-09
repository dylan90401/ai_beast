"""
Tests for evaluation module.
"""

import json

import pytest

from modules.evaluation.evaluator import Evaluator


@pytest.fixture
def evaluator():
    """Create evaluator instance with test config."""
    return Evaluator()


@pytest.fixture
def sample_predictions():
    """Sample predictions for testing."""
    return [
        {"id": "1", "value": "yes"},
        {"id": "2", "value": "no"},
        {"id": "3", "value": "yes"},
    ]


@pytest.fixture
def sample_ground_truth():
    """Sample ground truth for testing."""
    return [
        {"id": "1", "value": "yes"},
        {"id": "2", "value": "yes"},
        {"id": "3", "value": "yes"},
    ]


def test_evaluator_initialization(evaluator):
    """Test evaluator initializes correctly."""
    assert evaluator is not None
    assert evaluator.config is not None
    assert evaluator.metrics is not None


def test_accuracy_metric(evaluator, sample_predictions, sample_ground_truth):
    """Test accuracy metric calculation."""
    results = evaluator.evaluate(sample_predictions, sample_ground_truth)

    assert "accuracy" in results
    assert results["accuracy"] == pytest.approx(0.666, rel=0.01)


def test_exact_match_metric(evaluator):
    """Test exact match metric."""
    predictions = [{"id": "1", "value": "test"}]
    ground_truth = [{"id": "1", "value": "test"}]

    score = evaluator._exact_match(predictions, ground_truth)
    assert score == 1.0


def test_mismatched_lengths(evaluator):
    """Test error handling for mismatched prediction/ground truth lengths."""
    predictions = [{"id": "1", "value": "yes"}]
    ground_truth = [{"id": "1", "value": "yes"}, {"id": "2", "value": "no"}]

    with pytest.raises(ValueError):
        evaluator.evaluate(predictions, ground_truth)


def test_save_results(evaluator, tmp_path):
    """Test saving evaluation results."""
    results = {"scores": {"accuracy": 0.85}, "num_samples": 10}

    output_path = tmp_path / "results.json"
    evaluator.save_results(results, output_path)

    assert output_path.exists()

    with open(output_path) as f:
        loaded = json.load(f)

    assert loaded == results
