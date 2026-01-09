# Monitoring Module

Provides observability and health monitoring for AI Beast services.

## Features

- Service health checks
- Metrics collection
- System resource monitoring
- Log aggregation helpers

## Usage

```python
from modules.monitoring import check_service_health, collect_metrics
from pathlib import Path

# Check if Ollama is healthy
result = check_service_health("ollama", 11434)
print(result)

# Collect system metrics
metrics = collect_metrics(Path("/path/to/ai_beast"))
print(metrics)
```

## TODO(KRYPTOS)

- Add Prometheus metrics export
- Add OpenTelemetry integration
- Add alerting thresholds
- Add log parsing and analysis
