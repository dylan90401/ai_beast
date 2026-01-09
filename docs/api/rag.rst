RAG Module
==========

The RAG (Retrieval-Augmented Generation) module provides document
processing, embedding, and retrieval capabilities.

.. automodule:: modules.rag
   :members:
   :undoc-members:
   :show-inheritance:

Engine
------

.. automodule:: modules.rag.engine
   :members:
   :undoc-members:
   :show-inheritance:

Chunker
-------

.. automodule:: modules.rag.chunker
   :members:
   :undoc-members:
   :show-inheritance:

Parallel Ingestion
------------------

.. automodule:: modules.rag.parallel_ingest
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

Document Ingestion
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from modules.rag.parallel_ingest import ParallelIngestor

   async def ingest_documents():
       ingestor = ParallelIngestor(
           max_workers=4,
           chunk_size=512,
       )
       
       stats = await ingestor.ingest_directory(
           "./documents/",
           collection="my_docs",
           patterns=["*.pdf", "*.md", "*.txt"],
       )
       
       print(f"Processed {stats.total_documents} documents")
       print(f"Created {stats.total_chunks} chunks")

Querying Documents
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from modules.rag.engine import RAGEngine

   async def query_documents():
       engine = RAGEngine()
       
       result = await engine.query(
           question="What is the main topic?",
           collection="my_docs",
           top_k=5,
       )
       
       print("Answer:", result.answer)
       
       for source in result.sources:
           print(f"- {source.document}: {source.score:.2f}")

Custom Embeddings
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from modules.rag.embeddings import EmbeddingModel

   # Use a different embedding model
   embeddings = EmbeddingModel(
       model_name="sentence-transformers/all-mpnet-base-v2"
   )
   
   # Generate embeddings
   vectors = embeddings.encode([
       "First document",
       "Second document",
   ])
