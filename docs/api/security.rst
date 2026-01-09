Security Module
===============

The security module provides input validation, path safety, and
protection against common vulnerabilities.

.. automodule:: modules.security
   :members:
   :undoc-members:
   :show-inheritance:

Validators
----------

.. automodule:: modules.security.validators
   :members:
   :undoc-members:
   :show-inheritance:

Trust Module
------------

.. automodule:: modules.security.trust
   :members:
   :undoc-members:
   :show-inheritance:

Resilience
----------

Circuit Breakers
~~~~~~~~~~~~~~~~

.. automodule:: modules.resilience.circuit_breaker
   :members:
   :undoc-members:
   :show-inheritance:

Rate Limiting
~~~~~~~~~~~~~

.. automodule:: modules.ratelimit.limiter
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

Path Validation
~~~~~~~~~~~~~~~

.. code-block:: python

   from modules.security.validators import validate_safe_path

   # Validate file paths to prevent traversal attacks
   try:
       safe_path = validate_safe_path(
           user_input,
           base_dir="/app/data",
       )
       # Path is safe to use
   except ValueError as e:
       print(f"Invalid path: {e}")

URL Validation
~~~~~~~~~~~~~~

.. code-block:: python

   from modules.security.validators import validate_url

   # Validate URLs
   try:
       safe_url = validate_url(
           user_url,
           allowed_schemes=["https"],
           allowed_hosts=["api.example.com"],
       )
   except ValueError as e:
       print(f"Invalid URL: {e}")

Circuit Breaker
~~~~~~~~~~~~~~~

.. code-block:: python

   from modules.resilience.circuit_breaker import circuit_breaker

   @circuit_breaker(
       name="external_api",
       failure_threshold=5,
       timeout=30.0,
   )
   async def call_external_api():
       # If this fails 5 times, circuit opens
       # After 30s, it enters half-open state
       return await external_api.call()

Rate Limiting
~~~~~~~~~~~~~

.. code-block:: python

   from modules.ratelimit.limiter import rate_limit

   @rate_limit(
       requests=100,
       window=60,  # 100 requests per minute
   )
   async def api_endpoint(request):
       return process_request(request)
