# Evaluation Framework

The AI Beast evaluation framework provides comprehensive workspace assessment capabilities.

## Features

- **System Health**: Validates Python version, directory structure, and project configuration
- **Docker Services**: Checks Docker daemon, Docker Compose, and service configurations
- **Configuration**: Validates workspace configuration files and settings
- **Extensions**: Evaluates installed extensions and their status

## Usage

### CLI Commands

Run all evaluations:
```bash
./bin/beast eval
```

Run specific category:
```bash
./bin/beast eval --category system
./bin/beast eval --category docker
./bin/beast eval --category config
./bin/beast eval --category extensions
```

### Output Formats

Text format (default):
```bash
./bin/beast eval --format text
```

JSON format:
```bash
./bin/beast eval --format json
```

Save report to file:
```bash
./bin/beast eval --save .cache/evaluation-report.txt
./bin/beast eval --format json --save .cache/evaluation-report.json
```

## Python API

```python
from pathlib import Path
from modules.evaluation import Evaluator

# Initialize evaluator
evaluator = Evaluator(Path.cwd())

# Run all evaluations
results = evaluator.run_all_evaluations()

# Run specific evaluation
system_result = evaluator.evaluate_system_health()
docker_result = evaluator.evaluate_docker_services()
config_result = evaluator.evaluate_configuration()
extensions_result = evaluator.evaluate_extensions()

# Generate report
text_report = evaluator.generate_report("text")
json_report = evaluator.generate_report("json")

# Save report
evaluator.save_report("report.txt", "text")
evaluator.save_report("report.json", "json")
```

## Evaluation Categories

### System Health
- Python version (>= 3.11)
- Required directories (beast, modules, compose, config)
- pyproject.toml presence

### Docker Services
- Docker daemon accessibility
- Docker Compose availability
- Compose configuration files

### Configuration
- Config directory structure
- Resource configuration files (models.json, allowlists.json)

### Extensions
- Extensions directory
- Installed extension count and listing

## Metric Status

Each metric can have one of four statuses:
- **PASS** (✓): Metric passed successfully
- **FAIL** (✗): Metric failed, requires attention
- **WARN** (⚠): Metric has warnings, not critical
- **SKIP** (○): Metric was skipped

## Report Format

### Text Format
```
============================================================
AI BEAST WORKSPACE EVALUATION REPORT
============================================================
Generated: 2026-01-07T08:00:00.000000

SYSTEM HEALTH
------------------------------------------------------------
Duration: 0.05s
Summary: 5/5 passed

  ✓ python_version: Python 3.11.0
  ✓ directory_beast: Directory exists: beast
  ✓ directory_modules: Directory exists: modules
  ...

============================================================
```

### JSON Format
```json
{
  "results": [
    {
      "category": "system_health",
      "metrics": [
        {
          "name": "python_version",
          "status": "pass",
          "score": null,
          "message": "Python 3.11.0",
          "details": {},
          "timestamp": "2026-01-07T08:00:00.000000"
        }
      ],
      "summary": {
        "total": 5,
        "passed": 5,
        "failed": 0,
        "warnings": 0,
        "skipped": 0,
        "pass_rate": 1.0
      },
      "duration_seconds": 0.05,
      "timestamp": "2026-01-07T08:00:00.000000"
    }
  ],
  "timestamp": "2026-01-07T08:00:00.000000"
}
```

## Configuration

Configuration is stored in `eval_config.json`:
- Enable/disable specific evaluation categories
- Configure thresholds for pass rates
- Set default output formats and report locations

## Extending the Framework

To add custom evaluations:

1. Add new method to `Evaluator` class:
```python
def evaluate_custom_category(self) -> EvaluationResult:
    start_time = time.time()
    result = EvaluationResult(category="custom_category")
    
    # Add your checks
    result.add_metric(MetricResult(
        name="custom_check",
        status=MetricStatus.PASS,
        message="Custom check passed"
    ))
    
    result.duration_seconds = time.time() - start_time
    result.compute_summary()
    self.results.append(result)
    return result
```

2. Update `run_all_evaluations()` to include new category

3. Add CLI option in `beast/cli.py` if needed
