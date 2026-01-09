Beast CLI
=========

The Beast CLI provides command-line access to AI Beast functionality.

.. automodule:: beast.cli
   :members:
   :undoc-members:
   :show-inheritance:

Commands
--------

Model Commands
~~~~~~~~~~~~~~

.. code-block:: bash

   # List available models
   beast model list

   # Pull a model
   beast model pull llama3.2

   # Show model info
   beast model info llama3.2

   # Remove a model
   beast model rm phi3:mini

   # Update all models
   beast model update-all

RAG Commands
~~~~~~~~~~~~

.. code-block:: bash

   # Ingest documents
   beast rag ingest ./documents/

   # Query documents
   beast rag query "What is the main topic?"

   # List collections
   beast rag collections

   # Clear a collection
   beast rag clear my_collection

Service Commands
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Check service status
   beast status

   # Start services
   beast start

   # Stop services
   beast stop

   # Restart services
   beast restart

   # View logs
   beast logs [service]

Extension Commands
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # List extensions
   beast extension list

   # Enable extension
   beast extension enable open_webui

   # Disable extension
   beast extension disable n8n

   # Show extension status
   beast extension status

Health Commands
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Run health checks
   beast health

   # Detailed health check
   beast health --verbose

   # Check specific service
   beast health ollama

Chat Commands
~~~~~~~~~~~~~

.. code-block:: bash

   # Interactive chat
   beast chat llama3.2

   # One-shot generation
   beast generate llama3.2 "Hello, world!"

   # With options
   beast generate llama3.2 "Write code" --temperature 0.2
