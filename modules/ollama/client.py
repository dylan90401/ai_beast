"""Enhanced Ollama client with full API support.

Provides an async interface for interacting with the Ollama API,
including chat, generation, embeddings, and model management.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Callable

import aiohttp

from modules.container import AppContext
from modules.logging_config import get_logger

logger = get_logger(__name__)


class OllamaClient:
    """Enhanced Ollama API client.

    Usage:
        context = AppContext.from_env()
        async with OllamaClient(context) as client:
            response = await client.chat("llama3.2:latest", messages)
            print(response["message"]["content"])
    """

    def __init__(self, context: AppContext | None = None, base_url: str | None = None):
        """Initialize Ollama client.

        Args:
            context: Application context (optional if base_url provided)
            base_url: Direct URL to Ollama server (overrides context)
        """
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif context:
            self.base_url = context.ollama_url.rstrip("/")
        else:
            self.base_url = "http://127.0.0.1:11434"

        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> OllamaClient:
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    # ==================== Generation ====================

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        template: str | None = None,
        context: list[int] | None = None,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        format: str | None = None,
        raw: bool = False,
        keep_alive: str | None = None,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Generate completion from a model.

        Args:
            model: Model name
            prompt: Prompt text
            system: System prompt
            template: Prompt template
            context: Context from previous response
            stream: Whether to stream response
            options: Model options (temperature, top_p, etc.)
            format: Response format ("json" for JSON mode)
            raw: Skip prompt template
            keep_alive: How long to keep model loaded

        Returns:
            Response dict or async iterator of response chunks
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }

        if system:
            payload["system"] = system
        if template:
            payload["template"] = template
        if context:
            payload["context"] = context
        if options:
            payload["options"] = options
        if format:
            payload["format"] = format
        if raw:
            payload["raw"] = raw
        if keep_alive:
            payload["keep_alive"] = keep_alive

        if stream:
            return self._stream_response("/api/generate", payload)
        return await self._request("/api/generate", payload)

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        stream: bool = False,
        options: dict[str, Any] | None = None,
        format: str | None = None,
        keep_alive: str | None = None,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """Chat with a model.

        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream response
            options: Model options (temperature, top_p, etc.)
            format: Response format ("json" for JSON mode)
            keep_alive: How long to keep model loaded

        Returns:
            Response dict or async iterator of response chunks
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if options:
            payload["options"] = options
        if format:
            payload["format"] = format
        if keep_alive:
            payload["keep_alive"] = keep_alive

        if stream:
            return self._stream_response("/api/chat", payload)
        return await self._request("/api/chat", payload)

    # ==================== Embeddings ====================

    async def embeddings(
        self,
        model: str,
        prompt: str | list[str],
        options: dict[str, Any] | None = None,
        keep_alive: str | None = None,
    ) -> dict[str, Any]:
        """Generate embeddings.

        Args:
            model: Model name (e.g., "nomic-embed-text")
            prompt: Single prompt or list of prompts
            options: Model options
            keep_alive: How long to keep model loaded

        Returns:
            Dict with 'embedding' or 'embeddings' key
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }

        if options:
            payload["options"] = options
        if keep_alive:
            payload["keep_alive"] = keep_alive

        return await self._request("/api/embeddings", payload)

    # ==================== Model Management ====================

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models.

        Returns:
            List of model dicts with name, size, digest, etc.
        """
        result = await self._request("/api/tags", method="GET")
        return result.get("models", [])

    async def show_model(self, name: str) -> dict[str, Any]:
        """Show model information.

        Args:
            name: Model name

        Returns:
            Model info including parameters, template, license
        """
        return await self._request("/api/show", {"name": name})

    async def pull_model(
        self,
        name: str,
        insecure: bool = False,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Pull a model from registry.

        Args:
            name: Model name
            insecure: Allow insecure connections
            progress_callback: Callback for progress updates

        Returns:
            Final status dict
        """
        payload = {
            "name": name,
            "insecure": insecure,
            "stream": True,
        }

        logger.info("ollama_pull_started", model=name)
        final_status: dict[str, Any] = {}

        async for chunk in self._stream_response("/api/pull", payload):
            if progress_callback:
                progress_callback(chunk)
            final_status = chunk

            if chunk.get("status") == "success":
                logger.info("ollama_pull_completed", model=name)

        return final_status

    async def push_model(
        self,
        name: str,
        insecure: bool = False,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Push a model to registry.

        Args:
            name: Model name
            insecure: Allow insecure connections
            progress_callback: Callback for progress updates

        Returns:
            Final status dict
        """
        payload = {
            "name": name,
            "insecure": insecure,
            "stream": True,
        }

        logger.info("ollama_push_started", model=name)
        final_status: dict[str, Any] = {}

        async for chunk in self._stream_response("/api/push", payload):
            if progress_callback:
                progress_callback(chunk)
            final_status = chunk

        return final_status

    async def create_model(
        self,
        name: str,
        modelfile: str | None = None,
        path: str | None = None,
        stream: bool = False,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Create a model from a Modelfile.

        Args:
            name: Name for the new model
            modelfile: Modelfile contents
            path: Path to Modelfile on server
            stream: Whether to stream creation status
            progress_callback: Callback for progress updates

        Returns:
            Status dict
        """
        payload: dict[str, Any] = {
            "name": name,
            "stream": stream,
        }

        if modelfile:
            payload["modelfile"] = modelfile
        if path:
            payload["path"] = path

        logger.info("ollama_create_started", model=name)

        if stream:
            final_status: dict[str, Any] = {}
            async for chunk in self._stream_response("/api/create", payload):
                if progress_callback:
                    progress_callback(chunk)
                final_status = chunk
            return final_status
        return await self._request("/api/create", payload)

    async def delete_model(self, name: str) -> dict[str, Any]:
        """Delete a model.

        Args:
            name: Model name

        Returns:
            Status dict
        """
        logger.info("ollama_delete", model=name)
        return await self._request("/api/delete", {"name": name}, method="DELETE")

    async def copy_model(self, source: str, destination: str) -> dict[str, Any]:
        """Copy a model.

        Args:
            source: Source model name
            destination: Destination model name

        Returns:
            Status dict
        """
        logger.info("ollama_copy", source=source, destination=destination)
        return await self._request(
            "/api/copy",
            {"source": source, "destination": destination},
        )

    # ==================== Status & Health ====================

    async def is_running(self) -> bool:
        """Check if Ollama server is running.

        Returns:
            True if server is reachable
        """
        try:
            await self._request("/api/tags", method="GET")
            return True
        except Exception:
            return False

    async def ps(self) -> list[dict[str, Any]]:
        """List running models.

        Returns:
            List of running model dicts
        """
        result = await self._request("/api/ps", method="GET")
        return result.get("models", [])

    async def version(self) -> str:
        """Get Ollama version.

        Returns:
            Version string
        """
        result = await self._request("/api/version", method="GET")
        return result.get("version", "unknown")

    # ==================== Blob Management ====================

    async def check_blob(self, digest: str) -> bool:
        """Check if a blob exists.

        Args:
            digest: Blob digest (sha256:...)

        Returns:
            True if blob exists
        """
        session = await self._ensure_session()
        url = f"{self.base_url}/api/blobs/{digest}"

        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ==================== Internal Methods ====================

    async def _request(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        method: str = "POST",
        timeout: int = 3600,
    ) -> dict[str, Any]:
        """Make HTTP request to Ollama API.

        Args:
            endpoint: API endpoint
            data: Request data
            method: HTTP method
            timeout: Request timeout in seconds

        Returns:
            Response dict

        Raises:
            aiohttp.ClientError: On request failure
        """
        session = await self._ensure_session()
        url = f"{self.base_url}{endpoint}"
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        try:
            if method == "GET":
                async with session.get(url, timeout=client_timeout) as resp:
                    resp.raise_for_status()
                    return await resp.json()

            elif method == "DELETE":
                async with session.delete(url, json=data, timeout=client_timeout) as resp:
                    if resp.content_type == "application/json":
                        return await resp.json()
                    return {"status": "success"}

            else:  # POST
                async with session.post(url, json=data, timeout=client_timeout) as resp:
                    resp.raise_for_status()
                    return await resp.json()

        except aiohttp.ClientResponseError as e:
            logger.error(
                "ollama_request_failed",
                endpoint=endpoint,
                status=e.status,
                message=e.message,
            )
            raise
        except Exception as e:
            logger.error("ollama_request_failed", endpoint=endpoint, error=str(e))
            raise

    async def _stream_response(
        self,
        endpoint: str,
        data: dict[str, Any],
        timeout: int = 3600,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream response from Ollama API.

        Args:
            endpoint: API endpoint
            data: Request data
            timeout: Request timeout in seconds

        Yields:
            Response chunks as dicts
        """
        session = await self._ensure_session()
        url = f"{self.base_url}{endpoint}"
        client_timeout = aiohttp.ClientTimeout(total=timeout)

        async with session.post(url, json=data, timeout=client_timeout) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                if line:
                    try:
                        yield json.loads(line.decode())
                    except json.JSONDecodeError:
                        continue


# ==================== Convenience Functions ====================


async def get_ollama_client(
    context: AppContext | None = None,
    base_url: str | None = None,
) -> OllamaClient:
    """Get an Ollama client instance.

    Args:
        context: Application context
        base_url: Direct URL to Ollama server

    Returns:
        OllamaClient instance
    """
    if context is None and base_url is None:
        try:
            from modules.container import get_context

            context = get_context()
        except ImportError:
            pass

    return OllamaClient(context=context, base_url=base_url)


async def quick_chat(
    model: str,
    prompt: str,
    system: str | None = None,
    base_url: str = "http://127.0.0.1:11434",
) -> str:
    """Quick chat with an Ollama model.

    Args:
        model: Model name
        prompt: User prompt
        system: System prompt
        base_url: Ollama server URL

    Returns:
        Response content string
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with OllamaClient(base_url=base_url) as client:
        response = await client.chat(model, messages)
        return response.get("message", {}).get("content", "")


async def quick_generate(
    model: str,
    prompt: str,
    base_url: str = "http://127.0.0.1:11434",
) -> str:
    """Quick generation with an Ollama model.

    Args:
        model: Model name
        prompt: Prompt text
        base_url: Ollama server URL

    Returns:
        Response text
    """
    async with OllamaClient(base_url=base_url) as client:
        response = await client.generate(model, prompt)
        return response.get("response", "")
