"""
Tests for agent runner module.
"""

import json

import pytest

from modules.agent.agent_runner import AgentRunner


@pytest.fixture
def agent_runner():
    """Create agent runner instance."""
    return AgentRunner(trace_enabled=False)


@pytest.fixture
def test_dataset(tmp_path):
    """Create temporary test dataset."""
    dataset_path = tmp_path / "test_dataset.jsonl"

    test_cases = [
        {"id": "1", "input": "What is 2+2?", "expected": "4"},
        {"id": "2", "input": "What color is the sky?", "expected": "blue"},
    ]

    with open(dataset_path, "w") as f:
        for case in test_cases:
            f.write(json.dumps(case) + "\n")

    return dataset_path


def test_agent_runner_initialization(agent_runner):
    """Test agent runner initializes correctly."""
    assert agent_runner is not None
    assert agent_runner.config is not None


def test_run_single(agent_runner):
    """Test running agent on single prompt."""
    result = agent_runner.run_single("Test prompt", test_id="test_1")

    assert result["test_id"] == "test_1"
    assert result["prompt"] == "Test prompt"
    assert "response" in result
    assert result["status"] == "success"


def test_run_batch(agent_runner, test_dataset, tmp_path):
    """Test running agent on batch of test cases."""
    output_path = tmp_path / "results.jsonl"

    results = agent_runner.run_batch(test_dataset, output_path)

    assert len(results) == 2
    assert all(r["status"] == "success" for r in results)
    assert output_path.exists()


def test_run_batch_missing_dataset(agent_runner, tmp_path):
    """Test error handling for missing dataset."""
    missing_path = tmp_path / "missing.jsonl"

    with pytest.raises(FileNotFoundError):
        agent_runner.run_batch(missing_path)
