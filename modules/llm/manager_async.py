"""Async version of LLM Manager for better performance.

Uses aiohttp for non-blocking HTTP operations and asyncio for
concurrent file I/O operations. This module provides an async
interface for model management operations.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp

from modules.container import AppContext
from modules.llm.manager import ModelInfo, ModelLocation
from modules.logging_config import get_logger

logger = get_logger(__name__)


class AsyncLLMManager:
    """Async LLM Manager with non-blocking I/O.

    Usage:
        context = AppContext.from_env()
        async with AsyncLLMManager(context) as manager:
            models = await manager.list_ollama_models_async()
            result = await manager.download_from_url_async("https://example.com/model.gguf")
    """

    def __init__(self, context: AppContext):
        """Initialize async LLM Manager.

        Args:
            context: Application context with configuration
        """
        self.context = context
        self.base_dir = context.base_dir
        self.models_dir = context.models_dir / "llm"
        self.heavy_dir = context.heavy_dir
        self._model_cache: dict[str, ModelInfo] = {}
        self._cache_time: float = 0
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> AsyncLLMManager:
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

    async def scan_local_models_async(self, force: bool = False) -> list[ModelInfo]:
        """Scan for local models asynchronously.

        Args:
            force: Force rescan even if cached

        Returns:
            List of ModelInfo for discovered models
        """
        # Use asyncio.to_thread for file I/O to avoid blocking
        return await asyncio.to_thread(self._scan_local_models_sync, force)

    def _scan_local_models_sync(self, force: bool) -> list[ModelInfo]:
        """Synchronous scan implementation.

        Args:
            force: Force rescan even if cached

        Returns:
            List of ModelInfo for discovered models
        """
        import time

        from modules.llm.manager import _extract_quant, _human_size

        # Check cache validity (60 seconds)
        if not force and self._model_cache and (time.time() - self._cache_time < 60):
            return list(self._model_cache.values())

        models: list[ModelInfo] = []

        # Scan internal models directory
        if self.models_dir.exists():
            models.extend(
                self._scan_directory(self.models_dir, ModelLocation.INTERNAL),
            )

        # Scan external models directory (if different)
        external_models_dir = self.heavy_dir / "models" / "llm"
        if (
            external_models_dir.exists()
            and external_models_dir != self.models_dir
        ):
            models.extend(
                self._scan_directory(external_models_dir, ModelLocation.EXTERNAL),
            )

        # Update cache
        self._model_cache = {m.name: m for m in models}
        self._cache_time = time.time()

        logger.info("local_models_scanned", count=len(models))
        return models

    def _scan_directory(
        self,
        directory: Path,
        location: ModelLocation,
    ) -> list[ModelInfo]:
        """Scan a directory for model files.

        Args:
            directory: Directory to scan
            location: Location type for discovered models

        Returns:
            List of ModelInfo for discovered models
        """
        from modules.llm.manager import _extract_quant, _human_size

        models: list[ModelInfo] = []
        extensions = {".gguf", ".safetensors", ".ggml", ".bin"}

        for file_path in directory.rglob("*"):
            if file_path.suffix.lower() in extensions and file_path.is_file():
                stat = file_path.stat()
                model = ModelInfo(
                    name=file_path.stem,
                    path=str(file_path),
                    size_bytes=stat.st_size,
                    size_human=_human_size(stat.st_size),
                    location=location,
                    model_type=file_path.suffix.lower().lstrip("."),
                    quantization=_extract_quant(file_path.name),
                    modified=stat.st_mtime,
                )
                models.append(model)

        return models

    async def download_from_url_async(
        self,
        url: str,
        filename: str | None = None,
        destination: ModelLocation = ModelLocation.INTERNAL,
        custom_path: str | None = None,
        progress_callback: Any | None = None,  # Callable[[dict], None]
    ) -> dict[str, Any]:
        """Download a model asynchronously.

        Args:
            url: URL to download from
            filename: Optional filename override
            destination: Where to save the model
            custom_path: Custom path if destination is CUSTOM
            progress_callback: Callback for progress updates

        Returns:
            Dict with 'ok', 'path', 'size_bytes', or 'error' keys
        """
        session = await self._ensure_session()

        logger.info("download_started", url=url, destination=destination.value)

        # Determine destination path
        if destination == ModelLocation.CUSTOM and custom_path:
            dest_dir = Path(custom_path)
        elif destination == ModelLocation.EXTERNAL:
            dest_dir = self.heavy_dir / "models" / "llm"
        else:
            dest_dir = self.models_dir

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename
        if not filename:
            filename = (
                url.split("/")[-1].split("?")[0]
                or f"model_{int(asyncio.get_event_loop().time())}.gguf"
            )

        # Sanitize filename
        filename = self._safe_filename(filename)

        dest_path = dest_dir / filename
        temp_path = dest_dir / f".{filename}.part"

        try:
            timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour timeout
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    error_msg = f"HTTP {resp.status}: {resp.reason}"
                    logger.error("download_failed", url=url, error=error_msg)
                    return {"ok": False, "error": error_msg}

                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(temp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(
                                {
                                    "downloaded": downloaded,
                                    "total": total,
                                    "percent": (
                                        (downloaded / total * 100) if total else 0
                                    ),
                                },
                            )

                # Move to final location
                await asyncio.to_thread(temp_path.rename, dest_path)

                logger.info(
                    "download_completed",
                    url=url,
                    path=str(dest_path),
                    size_bytes=downloaded,
                )

                return {
                    "ok": True,
                    "path": str(dest_path),
                    "size_bytes": downloaded,
                }

        except asyncio.CancelledError:
            logger.warning("download_cancelled", url=url)
            if temp_path.exists():
                await asyncio.to_thread(temp_path.unlink)
            return {"ok": False, "error": "Download cancelled"}

        except TimeoutError:
            logger.error("download_timeout", url=url)
            if temp_path.exists():
                await asyncio.to_thread(temp_path.unlink)
            return {"ok": False, "error": "Download timed out"}

        except Exception as e:
            logger.error("download_failed", url=url, error=str(e))
            if temp_path.exists():
                await asyncio.to_thread(temp_path.unlink)
            return {"ok": False, "error": str(e)}

    async def list_ollama_models_async(self) -> list[ModelInfo]:
        """List Ollama models asynchronously.

        Returns:
            List of ModelInfo for Ollama models
        """
        session = await self._ensure_session()

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(
                f"{self.context.ollama_url}/api/tags",
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "ollama_list_failed",
                        status=resp.status,
                        reason=resp.reason,
                    )
                    return []

                data = await resp.json()
                models: list[ModelInfo] = []

                for m in data.get("models", []):
                    info = ModelInfo(
                        name=m.get("name", "unknown"),
                        path=f"ollama:{m.get('name')}",
                        size_bytes=m.get("size", 0),
                        size_human=self._human_size(m.get("size", 0)),
                        location=ModelLocation.OLLAMA,
                        model_type="ollama",
                        metadata=m,
                    )
                    models.append(info)

                logger.info("ollama_models_listed", count=len(models))
                return models

        except asyncio.CancelledError:
            return []
        except Exception as e:
            logger.error("ollama_list_failed", error=str(e))
            return []

    async def pull_ollama_model_async(
        self,
        model_name: str,
        progress_callback: Any | None = None,  # Callable[[dict], None]
    ) -> dict[str, Any]:
        """Pull an Ollama model asynchronously.

        Args:
            model_name: Name of model to pull
            progress_callback: Callback for progress updates

        Returns:
            Dict with 'ok', 'model', or 'error' keys
        """
        session = await self._ensure_session()

        logger.info("ollama_pull_started", model=model_name)

        try:
            timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour for large models
            async with session.post(
                f"{self.context.ollama_url}/api/pull",
                json={"name": model_name, "stream": True},
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    error_msg = f"HTTP {resp.status}: {resp.reason}"
                    logger.error(
                        "ollama_pull_failed",
                        model=model_name,
                        error=error_msg,
                    )
                    return {"ok": False, "error": error_msg}

                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode())
                        if progress_callback:
                            progress_callback(data)

                        if data.get("status") == "success":
                            logger.info(
                                "ollama_pull_completed",
                                model=model_name,
                            )
                            return {"ok": True, "model": model_name}
                    except json.JSONDecodeError:
                        continue

                return {"ok": True, "model": model_name}

        except asyncio.CancelledError:
            logger.warning("ollama_pull_cancelled", model=model_name)
            return {"ok": False, "error": "Pull cancelled"}
        except Exception as e:
            logger.error("ollama_pull_failed", model=model_name, error=str(e))
            return {"ok": False, "error": str(e)}

    async def delete_ollama_model_async(self, model_name: str) -> dict[str, Any]:
        """Delete an Ollama model asynchronously.

        Args:
            model_name: Name of model to delete

        Returns:
            Dict with 'ok' or 'error' keys
        """
        session = await self._ensure_session()

        logger.info("ollama_delete_started", model=model_name)

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.delete(
                f"{self.context.ollama_url}/api/delete",
                json={"name": model_name},
                timeout=timeout,
            ) as resp:
                if resp.status == 200:
                    logger.info("ollama_delete_completed", model=model_name)
                    return {"ok": True}
                error_msg = f"HTTP {resp.status}: {resp.reason}"
                logger.error(
                    "ollama_delete_failed",
                    model=model_name,
                    error=error_msg,
                )
                return {"ok": False, "error": error_msg}

        except Exception as e:
            logger.error("ollama_delete_failed", model=model_name, error=str(e))
            return {"ok": False, "error": str(e)}

    async def ollama_running_async(self) -> bool:
        """Check if Ollama is running asynchronously.

        Returns:
            True if Ollama is reachable
        """
        session = await self._ensure_session()

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.get(
                f"{self.context.ollama_url}/api/tags",
                timeout=timeout,
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def get_storage_info_async(self) -> dict[str, Any]:
        """Get storage information asynchronously.

        Returns:
            Dict with storage stats for each location
        """
        return await asyncio.to_thread(self._get_storage_info_sync)

    def _get_storage_info_sync(self) -> dict[str, Any]:
        """Synchronous storage info implementation."""
        import shutil

        info: dict[str, Any] = {}

        for name, path in [
            ("internal", self.models_dir),
            ("external", self.heavy_dir / "models" / "llm"),
        ]:
            if path.exists():
                try:
                    usage = shutil.disk_usage(path)
                    info[name] = {
                        "path": str(path),
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "total_human": self._human_size(usage.total),
                        "used_human": self._human_size(usage.used),
                        "free_human": self._human_size(usage.free),
                    }
                except OSError as e:
                    info[name] = {"path": str(path), "error": str(e)}
            else:
                info[name] = {"path": str(path), "exists": False}

        return info

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convert bytes to human readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Human readable size string
        """
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Make filename safe for filesystem.

        Args:
            name: Original filename

        Returns:
            Sanitized filename safe for filesystem
        """
        import re
        import unicodedata

        # Normalize unicode
        name = unicodedata.normalize("NFKC", name)

        # Remove path separators and null bytes
        name = name.replace("/", "_").replace("\\", "_").replace("\x00", "")

        # Remove or replace unsafe characters
        name = re.sub(r'[<>:"|?*]', "_", name)

        # Limit length (255 is typical filesystem limit)
        if len(name) > 200:
            ext = Path(name).suffix
            name = name[: 200 - len(ext)] + ext

        # Ensure not empty
        if not name or name.isspace():
            name = "unnamed_model.gguf"

        return name


async def get_async_llm_manager(context: AppContext | None = None) -> AsyncLLMManager:
    """Get an async LLM manager instance.

    Args:
        context: Optional application context (uses global if not provided)

    Returns:
        AsyncLLMManager instance
    """
    if context is None:
        from modules.container import get_context

        context = get_context()
    return AsyncLLMManager(context)
