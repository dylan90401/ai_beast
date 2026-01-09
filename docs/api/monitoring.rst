Monitoring Module
=================

The monitoring module provides metrics export, health checks,
and observability features.

.. automodule:: modules.monitoring
   :members:
   :undoc-members:
   :show-inheritance:

Metrics Exporter
----------------

.. automodule:: modules.monitoring.exporter
   :members:
   :undoc-members:
   :show-inheritance:

Health Checks
-------------

.. automodule:: modules.health.checker
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

Custom Metrics
~~~~~~~~~~~~~~

.. code-block:: python

   from modules.monitoring.exporter import (
       MetricsRegistry,
       Counter,
       Histogram,
       timed,
   )

   registry = MetricsRegistry()

   # Create a counter
   requests_total = registry.counter(
       "api_requests_total",
       "Total API requests",
       labels=["endpoint", "method"],
   )

   # Create a histogram
   request_duration = registry.histogram(
       "api_request_duration_seconds",
       "Request duration",
       buckets=[0.1, 0.5, 1.0, 5.0],
   )

   # Use metrics
   requests_total.inc(endpoint="/api/chat", method="POST")
   
   with request_duration.time():
       process_request()

Decorator
~~~~~~~~~

.. code-block:: python

   from modules.monitoring.exporter import timed

   @timed("function_duration_seconds")
   async def my_function():
       # Automatically tracks execution time
       return await do_work()

Health Checks
~~~~~~~~~~~~~

.. code-block:: python

   from modules.health.checker import (
       SystemHealthChecker,
       OllamaHealthChecker,
       QdrantHealthChecker,
   )

   # Create health checkers
   checkers = [
       SystemHealthChecker(),
       OllamaHealthChecker("http://localhost:11434"),
       QdrantHealthChecker("http://localhost:6333"),
   ]

   # Check all services
   async def health_endpoint():
       results = []
       for checker in checkers:
           result = await checker.check()
           results.append(result.to_dict())
       
       all_healthy = all(r["status"] == "healthy" for r in results)
       return {"healthy": all_healthy, "checks": results}

Prometheus Integration
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from modules.monitoring.exporter import MetricsServer

   # Start metrics server
   server = MetricsServer(port=9090)
   await server.start()

   # Metrics available at http://localhost:9090/metrics

Grafana Dashboards
~~~~~~~~~~~~~~~~~~

AI Beast includes pre-configured Grafana dashboards:

- **Overview Dashboard** - System health, request rates, error rates
- **Model Dashboard** - Model performance, token usage, latency
- **RAG Dashboard** - Ingestion stats, query performance, cache hits

Import dashboards from ``config/grafana/dashboards/``.
