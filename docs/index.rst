.. AI Beast documentation master file

=======================================
AI Beast - Local AI Infrastructure
=======================================

.. image:: _static/logo.png
   :alt: AI Beast Logo
   :align: center
   :width: 200px

AI Beast is a comprehensive local AI infrastructure manager that provides
tools for managing LLM models, RAG pipelines, and AI workflows.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/installation
   getting-started/quickstart
   getting-started/configuration

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/models
   user-guide/rag
   user-guide/extensions
   user-guide/dashboard

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/modules
   api/beast
   api/llm
   api/rag
   api/security
   api/monitoring

.. toctree::
   :maxdepth: 2
   :caption: Operations

   operations/deployment
   operations/monitoring
   operations/backup
   operations/troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Development

   development/contributing
   development/architecture
   development/testing

.. toctree::
   :maxdepth: 1
   :caption: About

   changelog
   license


Features
--------

🦙 **Model Management**
   Download, configure, and manage LLM models from multiple sources
   including Ollama, Hugging Face, and custom repositories.

📚 **RAG Pipeline**
   Build retrieval-augmented generation pipelines with Qdrant
   vector database integration and intelligent document processing.

🔌 **Extensible Architecture**
   Add functionality through extensions: Open WebUI, n8n workflows,
   Jupyter notebooks, monitoring stacks, and more.

🎛️ **Dashboard**
   Web-based dashboard for monitoring, configuration, and
   real-time service management.

🔒 **Security First**
   Input validation, path traversal protection, rate limiting,
   and circuit breakers for production-ready deployments.


Quick Example
-------------

.. code-block:: python

   from modules.ollama.client import OllamaClient

   # Initialize client
   client = OllamaClient()

   # Generate text
   response = await client.generate(
       model="llama3.2",
       prompt="Explain quantum computing in simple terms",
   )
   print(response.response)


Installation
------------

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/dylan90401/ai_beast.git
   cd ai_beast

   # Run bootstrap
   make bootstrap

   # Start services
   make up


Indices and Tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
