"""LLM Model Manager — handles Ollama + local GGUF/safetensors files.

Features:
- Auto-detect models dropped into MODELS_DIR
- Download models from URL
- Ollama integration (pull/list/delete)
- Model location management (internal/external/custom)
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from modules.core.metadata_db import get_metadata_db

class ModelLocation(Enum):
    """Where models are stored."""
    INTERNAL = "internal"   # BASE_DIR/models/llm
    EXTERNAL = "external"   # HEAVY_DIR/models/llm (if different)
    OLLAMA = "ollama"       # Managed by Ollama
    CUSTOM = "custom"       # User-specified path


@dataclass
class ModelInfo:
    """Model metadata."""
    name: str
    path: str
    size_bytes: int = 0
    size_human: str = ""
    location: ModelLocation = ModelLocation.INTERNAL
    model_type: str = "unknown"  # gguf, safetensors, ollama
    quantization: str = ""       # Q4_K_M, Q8_0, etc.
    modified: float = 0.0
    sha256: str = ""
    source_url: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "size_human": self.size_human,
            "location": self.location.value,
            "model_type": self.model_type,
            "quantization": self.quantization,
            "modified": self.modified,
            "sha256": self.sha256,
            "source_url": self.source_url,
            "metadata": self.metadata,
        }


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _extract_quant(filename: str) -> str:
    """Extract quantization from filename (e.g., Q4_K_M, Q8_0)."""
    patterns = [
        r"[_-](Q[0-9]_[A-Z0-9_]+)",
        r"[_-](q[0-9]_[a-z0-9_]+)",
        r"[_-](fp16|fp32|f16|f32|bf16)",
        r"[_-]([0-9]+bit)",
    ]
    for pat in patterns:
        m = re.search(pat, filename, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return ""


def _validate_download_url(url: str) -> tuple[bool, str]:
    raw = (url or "").strip()
    if not raw:
        return False, "URL is required"
    if any(ch.isspace() for ch in raw):
        return False, "URL cannot contain whitespace"
    if len(raw) > 2048:
        return False, "URL too long"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http or https"
    if not parsed.netloc:
        return False, "URL must include a hostname"

    # Disallow credentials in URLs (reduces accidental secret leakage)
    if parsed.username or parsed.password:
        return False, "URL must not include credentials"

    allow_local = os.environ.get("AI_BEAST_ALLOW_LOCAL_URLS", "0") in ("1", "true", "True")
    if not allow_local:
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"):
            return False, "Local URLs are not allowed"

        # Block private/local IP literals (SSRF hardening)
        try:
            ip = ipaddress.ip_address(host)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False, "Local/private IPs are not allowed"
        except ValueError:
            # Not an IP literal; hostname checks above are sufficient here.
            pass
    return True, raw


def _safe_filename(name: str) -> str:
    if not name:
        return ""
    if any(sep in name for sep in ("/", "\\")):
        return ""
    cleaned = Path(name).name
    if cleaned in (".", "..") or "\x00" in cleaned or cleaned != name:
        return ""
    return cleaned


def _resolve_dest(dest_dir: Path, filename: str) -> tuple[bool, Path | str]:
    try:
        dest_dir = dest_dir.expanduser().resolve()
    except Exception:
        return False, "Invalid destination directory"
    dest_path = (dest_dir / filename).resolve()
    try:
        dest_path.relative_to(dest_dir)
    except ValueError:
        return False, "Destination path escapes target directory"
    return True, dest_path


class LLMManager:
    """Manages LLM models: Ollama + local files."""

    MODEL_EXTENSIONS = {".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx"}
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else self._detect_base_dir()
        self._load_paths()
        self._downloads: dict[str, dict] = {}  # track active downloads
        self._download_lock = threading.Lock()
        self._model_cache: dict[str, ModelInfo] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 30.0  # seconds

        # Optional: file-system watcher that invalidates scan cache on changes.
        # Disabled by default to avoid extra background threads unless desired.
        self._cache_watcher = None
        if os.environ.get("AI_BEAST_ENABLE_FS_WATCHER", "0") in ("1", "true", "True"):
            try:
                from modules.cache.watcher import CacheManager

                cm = CacheManager(auto_start=True)
                cache_key = "llm_scan"
                cm.create_cache(cache_key)

                def _invalidate_scan_cache() -> None:
                    self._cache_time = 0

                cm.on_invalidate(cache_key, _invalidate_scan_cache)

                patterns = {f"*{ext}" for ext in self.MODEL_EXTENSIONS}
                cm.watch_directory(self.llm_models_dir, cache_key=cache_key, patterns=patterns)
                cm.watch_directory(self.models_dir, cache_key=cache_key, patterns=patterns)
                cm.watch_directory(self.heavy_dir / "models" / "llm", cache_key=cache_key, patterns=patterns)
                self._cache_watcher = cm
            except Exception:
                # Watcher is a best-effort enhancement; never break core functionality.
                self._cache_watcher = None

    def _detect_base_dir(self) -> Path:
        """Detect BASE_DIR from environment or default."""
        if os.getenv("BASE_DIR"):
            return Path(os.environ["BASE_DIR"])
        # Walk up from this file to find project root
        p = Path(__file__).resolve()
        for parent in p.parents:
            if (parent / "bin" / "beast").exists():
                return parent
        return Path.cwd()

    def _load_paths(self):
        """Load paths from paths.env."""
        paths_env = self.base_dir / "config" / "paths.env"
        env_vars = {}
        if paths_env.exists():
            for line in paths_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    # Expand $VAR references
                    for var, val in list(env_vars.items()):
                        v = v.replace(f"${var}", val).replace(f"${{{var}}}", val)
                    env_vars[k] = v

        self.heavy_dir = Path(env_vars.get("HEAVY_DIR", str(self.base_dir)))
        self.models_dir = Path(env_vars.get("MODELS_DIR", str(self.base_dir / "models")))
        self.llm_models_dir = Path(env_vars.get("LLM_MODELS_DIR", str(self.models_dir / "llm")))
        self.ollama_models_dir = Path(env_vars.get("OLLAMA_MODELS", str(self.llm_models_dir / "ollama")))
        self.cache_dir = Path(env_vars.get("CACHE_DIR", str(self.base_dir / "cache")))
        self.llm_cache_dir = Path(env_vars.get("LLM_CACHE_DIR", str(self.cache_dir / "llm")))

        # Ensure directories exist
        for d in [self.models_dir, self.llm_models_dir, self.llm_cache_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Local Model Scanning (auto-detect dropped files)
    # -------------------------------------------------------------------------

    def scan_local_models(self, force: bool = False) -> list[ModelInfo]:
        """Scan for local model files (GGUF, safetensors, etc.)."""
        if not force and (time.time() - self._cache_time) < self._cache_ttl:
            return [m for m in self._model_cache.values() if m.location != ModelLocation.OLLAMA]

        models = []
        scan_dirs = [self.llm_models_dir, self.models_dir]

        # Add unique paths only
        seen_paths: set[str] = set()
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for ext in self.MODEL_EXTENSIONS:
                for fp in scan_dir.rglob(f"*{ext}"):
                    if str(fp) in seen_paths:
                        continue
                    seen_paths.add(str(fp))
                    try:
                        stat = fp.stat()
                        # Determine location
                        if str(fp).startswith(str(self.base_dir)):
                            loc = ModelLocation.INTERNAL
                        elif str(fp).startswith(str(self.heavy_dir)):
                            loc = ModelLocation.EXTERNAL
                        else:
                            loc = ModelLocation.CUSTOM

                        info = ModelInfo(
                            name=fp.stem,
                            path=str(fp),
                            size_bytes=stat.st_size,
                            size_human=_human_size(stat.st_size),
                            location=loc,
                            model_type=ext.lstrip("."),
                            quantization=_extract_quant(fp.name),
                            modified=stat.st_mtime,
                        )
                        models.append(info)
                        self._model_cache[str(fp)] = info
                    except OSError:
                        continue

        self._cache_time = time.time()
        return models

    # -------------------------------------------------------------------------
    # Ollama Integration
    # -------------------------------------------------------------------------

    def _ollama_api(self, endpoint: str, method: str = "GET", data: dict | None = None) -> dict:
        """Call Ollama API."""
        url = f"{self.OLLAMA_HOST}/api/{endpoint}"
        headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(url, method=method, headers=headers)
        if data:
            req.data = json.dumps(data).encode("utf-8")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"error": str(e), "ok": False}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response", "ok": False}

    def ollama_running(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = self._ollama_api("tags")
            return "models" in resp or "error" not in resp
        except Exception:
            return False

    def list_ollama_models(self) -> list[ModelInfo]:
        """List models managed by Ollama."""
        resp = self._ollama_api("tags")
        if "error" in resp:
            return []

        models = []
        for m in resp.get("models", []):
            name = m.get("name", "unknown")
            size = m.get("size", 0)
            info = ModelInfo(
                name=name,
                path=f"ollama:{name}",
                size_bytes=size,
                size_human=_human_size(size),
                location=ModelLocation.OLLAMA,
                model_type="ollama",
                modified=0,
                metadata={
                    "digest": m.get("digest", ""),
                    "modified_at": m.get("modified_at", ""),
                    "details": m.get("details", {}),
                },
            )
            models.append(info)
            self._model_cache[f"ollama:{name}"] = info

        return models

    def pull_ollama_model(self, model_name: str, callback: Callable[[dict], None] | None = None) -> dict:
        """Pull a model from Ollama registry."""
        # For streaming, we need to handle NDJSON
        url = f"{self.OLLAMA_HOST}/api/pull"
        data = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    if line.strip():
                        try:
                            status = json.loads(line.decode("utf-8"))
                            if callback:
                                callback(status)
                            if status.get("status") == "success":
                                return {"ok": True, "model": model_name}
                        except json.JSONDecodeError:
                            continue
            return {"ok": True, "model": model_name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_ollama_model(self, model_name: str) -> dict:
        """Delete an Ollama model."""
        resp = self._ollama_api("delete", method="DELETE", data={"name": model_name})
        if "error" in resp:
            return {"ok": False, "error": resp["error"]}
        return {"ok": True, "model": model_name}

    def list_available_ollama_models(self) -> list[dict]:
        """List popular models available from Ollama library."""
        # Static list of popular models (Ollama doesn't have a public API for this)
        return [
            {"name": "llama3.2:3b", "desc": "Meta Llama 3.2 3B", "size": "2.0GB"},
            {"name": "llama3.2:1b", "desc": "Meta Llama 3.2 1B", "size": "1.3GB"},
            {"name": "llama3.1:8b", "desc": "Meta Llama 3.1 8B", "size": "4.7GB"},
            {"name": "llama3.1:70b", "desc": "Meta Llama 3.1 70B", "size": "40GB"},
            {"name": "mistral:7b", "desc": "Mistral 7B", "size": "4.1GB"},
            {"name": "mixtral:8x7b", "desc": "Mixtral 8x7B MoE", "size": "26GB"},
            {"name": "codellama:7b", "desc": "Code Llama 7B", "size": "3.8GB"},
            {"name": "codellama:34b", "desc": "Code Llama 34B", "size": "19GB"},
            {"name": "deepseek-coder:6.7b", "desc": "DeepSeek Coder 6.7B", "size": "3.8GB"},
            {"name": "deepseek-coder-v2:16b", "desc": "DeepSeek Coder V2 16B", "size": "8.9GB"},
            {"name": "phi3:mini", "desc": "Microsoft Phi-3 Mini", "size": "2.3GB"},
            {"name": "phi3:medium", "desc": "Microsoft Phi-3 Medium", "size": "7.9GB"},
            {"name": "gemma2:9b", "desc": "Google Gemma 2 9B", "size": "5.5GB"},
            {"name": "gemma2:27b", "desc": "Google Gemma 2 27B", "size": "16GB"},
            {"name": "qwen2.5:7b", "desc": "Alibaba Qwen 2.5 7B", "size": "4.4GB"},
            {"name": "qwen2.5:72b", "desc": "Alibaba Qwen 2.5 72B", "size": "41GB"},
            {"name": "command-r:35b", "desc": "Cohere Command R 35B", "size": "20GB"},
            {"name": "nomic-embed-text", "desc": "Nomic Embed Text", "size": "274MB"},
            {"name": "mxbai-embed-large", "desc": "MixedBread Embed Large", "size": "670MB"},
            {"name": "all-minilm", "desc": "All-MiniLM-L6-v2", "size": "45MB"},
        ]

    # -------------------------------------------------------------------------
    # URL Download
    # -------------------------------------------------------------------------

    def download_from_url(
        self,
        url: str,
        filename: str | None = None,
        destination: ModelLocation = ModelLocation.INTERNAL,
        custom_path: str | None = None,
        callback: Callable[[dict], None] | None = None,
    ) -> dict:
        """Download a model from URL.

        Args:
            url: URL to download from
            filename: Optional filename (extracted from URL if not provided)
            destination: Where to save (INTERNAL, EXTERNAL, CUSTOM)
            custom_path: Required if destination is CUSTOM
            callback: Progress callback function

        Returns:
            dict with 'ok', 'path', 'error' keys
        """
        ok, cleaned_url = _validate_download_url(url)
        if not ok:
            return {"ok": False, "error": cleaned_url}
        parsed = urllib.parse.urlparse(cleaned_url)
        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # Determine filename
        if not filename:
            filename = cleaned_url.split("/")[-1].split("?")[0]
        filename = _safe_filename(filename or "")
        if not filename:
            filename = f"model_{int(time.time())}.gguf"
        if Path(filename).suffix.lower() not in self.MODEL_EXTENSIONS:
            return {"ok": False, "error": "Filename must be a model file (gguf/safetensors/bin/pt/pth/onnx)"}

        # Determine destination path
        if destination == ModelLocation.CUSTOM and custom_path:
            dest_dir = Path(custom_path)
            if not dest_dir.is_absolute():
                return {"ok": False, "error": "Custom path must be absolute"}
        elif destination == ModelLocation.EXTERNAL:
            dest_dir = self.heavy_dir / "models" / "llm"
        else:
            dest_dir = self.llm_models_dir

        ok, resolved = _resolve_dest(dest_dir, filename)
        if not ok:
            return {"ok": False, "error": resolved}
        dest_dir = resolved.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = resolved
        temp_path = dest_dir / f".{filename}.part"

        # Track download
        download_id = hashlib.md5(cleaned_url.encode()).hexdigest()[:8]
        with self._download_lock:
            if download_id in self._downloads:
                return {"ok": False, "error": "Download already in progress"}
            self._downloads[download_id] = {
                "url": cleaned_url,
                "path": str(dest_path),
                "progress": 0,
                "status": "starting",
            }
        try:
            get_metadata_db().record_event(
                "download",
                "model_download_started",
                {"download_id": download_id, "url": safe_url, "destination": destination.value},
            )
        except Exception:
            pass

        def _download():
            try:
                req = urllib.request.Request(cleaned_url)
                req.add_header("User-Agent", "AI-Beast/1.0")

                with urllib.request.urlopen(req, timeout=60) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0

                    with open(temp_path, "wb") as f:
                        while True:
                            chunk = resp.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            progress = (downloaded / total * 100) if total else 0
                            with self._download_lock:
                                self._downloads[download_id].update({
                                    "progress": progress,
                                    "downloaded": downloaded,
                                    "total": total,
                                    "status": "downloading",
                                })

                            if callback:
                                callback({
                                    "progress": progress,
                                    "downloaded": downloaded,
                                    "total": total,
                                    "downloaded_human": _human_size(downloaded),
                                    "total_human": _human_size(total),
                                })

                # Move to final location
                shutil.move(str(temp_path), str(dest_path))

                with self._download_lock:
                    self._downloads[download_id].update({
                        "progress": 100,
                        "status": "complete",
                        "path": str(dest_path),
                    })
                try:
                    get_metadata_db().record_event(
                        "download",
                        "model_download_complete",
                        {"download_id": download_id, "url": safe_url, "path": str(dest_path)},
                    )
                except Exception:
                    pass

                # Invalidate cache
                self._cache_time = 0

                if callback:
                    callback({"status": "complete", "path": str(dest_path)})

            except Exception as e:
                with self._download_lock:
                    self._downloads[download_id].update({
                        "status": "error",
                        "error": str(e),
                    })
                if temp_path.exists():
                    temp_path.unlink()
                if callback:
                    callback({"status": "error", "error": str(e)})
                try:
                    get_metadata_db().record_event(
                        "download",
                        "model_download_error",
                        {"download_id": download_id, "url": safe_url, "error": str(e)},
                    )
                except Exception:
                    pass

        thread = threading.Thread(target=_download, daemon=True)
        thread.start()

        return {
            "ok": True,
            "download_id": download_id,
            "path": str(dest_path),
            "message": "Download started",
        }

    def get_download_status(self, download_id: str | None = None) -> dict:
        """Get status of active downloads."""
        with self._download_lock:
            if download_id:
                return self._downloads.get(download_id, {"error": "Not found"})
            return dict(self._downloads)

    # -------------------------------------------------------------------------
    # Model Management
    # -------------------------------------------------------------------------

    def list_all_models(self, force_scan: bool = False) -> list[ModelInfo]:
        """List all models (local + Ollama)."""
        models = self.scan_local_models(force=force_scan)
        models.extend(self.list_ollama_models())
        return models

    def delete_local_model(self, path: str) -> dict:
        """Delete a local model file."""
        fp = Path(path).expanduser()

        # Resolve once for containment checks (blocks ../ traversal)
        try:
            fp_resolved = fp.resolve(strict=False)
        except (OSError, RuntimeError) as e:
            return {"ok": False, "error": f"Invalid path: {e}"}

        if not fp.exists():
            return {"ok": False, "error": "File not found"}
        if not fp.is_file():
            return {"ok": False, "error": "Path is not a file"}

        # Safety check: only delete from model directories (never from base_dir/heavy_dir root)
        heavy_models_dir = self.heavy_dir / "models" / "llm"
        allowed_parents = [
            self.llm_models_dir,
            self.models_dir,
            heavy_models_dir,
        ]
        allowed_resolved: list[Path] = []
        for parent in allowed_parents:
            try:
                allowed_resolved.append(parent.expanduser().resolve(strict=False))
            except OSError:
                continue

        if not allowed_resolved:
            return {"ok": False, "error": "No allowed model directories configured"}

        if not any(fp_resolved.is_relative_to(parent) for parent in allowed_resolved):
            return {"ok": False, "error": "Path not in allowed model directories"}

        # Additional defense: if fp is a symlink, only allow if resolved target is also in an allowed dir
        try:
            if fp.is_symlink() and not any(fp_resolved.is_relative_to(parent) for parent in allowed_resolved):
                return {"ok": False, "error": "Symlink target escapes allowed directories"}
        except OSError as e:
            return {"ok": False, "error": f"Unable to stat path: {e}"}

        try:
            fp.unlink()
            self._model_cache.pop(str(fp), None)
            self._cache_time = 0
            return {"ok": True, "path": str(fp)}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    def get_storage_info(self) -> dict:
        """Get storage information for model directories."""
        info = {}
        for name, path in [
            ("internal", self.llm_models_dir),
            ("external", self.heavy_dir / "models" / "llm"),
            ("models_root", self.models_dir),
        ]:
            if path.exists():
                try:
                    stat = shutil.disk_usage(path)
                    info[name] = {
                        "path": str(path),
                        "total": stat.total,
                        "used": stat.used,
                        "free": stat.free,
                        "total_human": _human_size(stat.total),
                        "used_human": _human_size(stat.used),
                        "free_human": _human_size(stat.free),
                        "percent_used": round(stat.used / stat.total * 100, 1) if stat.total else 0,
                    }
                except OSError:
                    info[name] = {"path": str(path), "error": "Cannot read"}
            else:
                info[name] = {"path": str(path), "exists": False}
        return info

    def move_model(self, src_path: str, destination: ModelLocation, custom_path: str | None = None) -> dict:
        """Move a model to a different location."""
        src = Path(src_path)
        if not src.exists():
            return {"ok": False, "error": "Source file not found"}

        if destination == ModelLocation.CUSTOM and custom_path:
            dest_dir = Path(custom_path)
        elif destination == ModelLocation.EXTERNAL:
            dest_dir = self.heavy_dir / "models" / "llm"
        else:
            dest_dir = self.llm_models_dir

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        if dest.exists():
            return {"ok": False, "error": "Destination file already exists"}

        try:
            shutil.move(str(src), str(dest))
            self._cache_time = 0
            return {"ok": True, "old_path": str(src), "new_path": str(dest)}
        except OSError as e:
            return {"ok": False, "error": str(e)}


# Module-level convenience instance
_manager: LLMManager | None = None


def get_manager() -> LLMManager:
    """Get or create singleton manager instance."""
    global _manager
    if _manager is None:
        _manager = LLMManager()
    return _manager
