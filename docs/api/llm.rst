LLM Module
==========

The LLM module provides interfaces for managing and interacting with
Large Language Models.

.. automodule:: modules.llm
   :members:
   :undoc-members:
   :show-inheritance:

Manager
-------

.. automodule:: modules.llm.manager
   :members:
   :undoc-members:
   :show-inheritance:

Async Manager
-------------

.. automodule:: modules.llm.manager_async
   :members:
   :undoc-members:
   :show-inheritance:

Ollama Client
-------------

.. automodule:: modules.ollama.client
   :members:
   :undoc-members:
   :show-inheritance:

Examples
--------

Basic Usage
~~~~~~~~~~~

.. code-block:: python

   from modules.ollama.client import OllamaClient

   async def generate_text():
       client = OllamaClient()
       
       response = await client.generate(
           model="llama3.2",
           prompt="Explain quantum computing",
           options={
               "temperature": 0.7,
               "top_p": 0.9,
           }
       )
       
       return response.response

Streaming
~~~~~~~~~

.. code-block:: python

   async def stream_response():
       client = OllamaClient()
       
       async for chunk in client.generate_stream(
           model="llama3.2",
           prompt="Write a short story",
       ):
           print(chunk.response, end="", flush=True)

Chat Conversation
~~~~~~~~~~~~~~~~~

.. code-block:: python

   async def chat():
       client = OllamaClient()
       
       messages = [
           {"role": "system", "content": "You are a helpful assistant."},
           {"role": "user", "content": "What is Python?"},
       ]
       
       response = await client.chat(
           model="llama3.2",
           messages=messages,
       )
       
       return response.message.content
