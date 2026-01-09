"""
Model catalog and registry system.

Provides centralized model metadata storage, search, and recommendations
using SQLite backend for persistence.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from modules.db.pool import get_pool
from modules.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================


class ModelFamily(str, Enum):
    """Model family/architecture."""

    LLAMA = "llama"
    MISTRAL = "mistral"
    GEMMA = "gemma"
    PHI = "phi"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    STARCODER = "starcoder"
    CODELLAMA = "codellama"
    SDXL = "sdxl"
    FLUX = "flux"
    WHISPER = "whisper"
    NOMIC = "nomic"
    BERT = "bert"
    OTHER = "other"


class ModelLicense(str, Enum):
    """Model license types."""

    MIT = "MIT"
    APACHE_2 = "Apache-2.0"
    GPL = "GPL"
    LLAMA = "Llama"
    GEMMA = "Gemma"
    QWEN = "Qwen"
    CC_BY_NC = "CC-BY-NC"
    CUSTOM = "Custom"
    UNKNOWN = "Unknown"


class ModelModality(str, Enum):
    """Model modalities/capabilities."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    CODE = "code"
    EMBEDDING = "embedding"
    MULTIMODAL = "multimodal"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ModelMetadata:
    """Complete model metadata."""

    # Identity
    id: str
    name: str
    version: str
    family: ModelFamily

    # Technical specs
    size_bytes: int
    parameter_count: int | None = None
    quantization: str | None = None
    context_length: int | None = None
    hidden_size: int | None = None
    num_layers: int | None = None

    # Source information
    source_url: str = ""
    source_repo: str = ""
    sha256: str = ""
    filename_pattern: str = ""

    # Legal
    license: ModelLicense = ModelLicense.UNKNOWN
    license_url: str = ""

    # Capabilities
    tags: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    modalities: list[ModelModality] = field(default_factory=list)

    # Quality metrics
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    recommended_use: str = ""
    limitations: str = ""
    training_data: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    author: str = ""
    organization: str = ""
    description: str = ""

    # Usage stats
    download_count: int = 0
    rating: float = 0.0
    reviews: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["family"] = self.family.value
        data["license"] = self.license.value
        data["modalities"] = [m.value if isinstance(m, ModelModality) else m for m in self.modalities]
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetadata:
        """Create from dictionary."""
        data = data.copy()
        data["family"] = ModelFamily(data["family"])
        data["license"] = ModelLicense(data["license"])
        data["modalities"] = [
            ModelModality(m) if isinstance(m, str) else m
            for m in data.get("modalities", [])
        ]
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)

    @property
    def size_human(self) -> str:
        """Human-readable size."""
        if self.size_bytes >= 1024**3:
            return f"{self.size_bytes / (1024**3):.2f} GB"
        elif self.size_bytes >= 1024**2:
            return f"{self.size_bytes / (1024**2):.2f} MB"
        else:
            return f"{self.size_bytes / 1024:.2f} KB"

    @property
    def params_human(self) -> str:
        """Human-readable parameter count."""
        if not self.parameter_count:
            return "Unknown"
        if self.parameter_count >= 1e12:
            return f"{self.parameter_count / 1e12:.1f}T"
        elif self.parameter_count >= 1e9:
            return f"{self.parameter_count / 1e9:.1f}B"
        elif self.parameter_count >= 1e6:
            return f"{self.parameter_count / 1e6:.1f}M"
        return str(self.parameter_count)


@dataclass
class ModelInstance:
    """A specific installation of a model."""

    id: int
    model_id: str
    path: str
    location: str
    installed_at: datetime
    last_used: datetime | None = None
    use_count: int = 0
    is_active: bool = True


# =============================================================================
# Model Registry
# =============================================================================


class ModelRegistry:
    """
    Centralized model registry with SQLite backend.

    Provides model metadata storage, search, recommendations,
    and instance tracking.
    """

    def __init__(self, db_path: Path | str | None = None):
        """
        Initialize registry.

        Args:
            db_path: Path to SQLite database (defaults to data/registry/models.db)
        """
        if db_path is None:
            from modules.container import get_container

            container = get_container()
            context = container.get("context")
            if context:
                db_path = Path(context.data_dir) / "registry" / "models.db"
            else:
                db_path = Path("data/registry/models.db")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._pool = get_pool(self.db_path)
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        with self._pool.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    family TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    parameter_count INTEGER,
                    quantization TEXT,
                    context_length INTEGER,
                    hidden_size INTEGER,
                    num_layers INTEGER,
                    source_url TEXT,
                    source_repo TEXT,
                    sha256 TEXT,
                    filename_pattern TEXT,
                    license TEXT,
                    license_url TEXT,
                    tags TEXT,
                    languages TEXT,
                    modalities TEXT,
                    benchmark_scores TEXT,
                    recommended_use TEXT,
                    limitations TEXT,
                    training_data TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    author TEXT,
                    organization TEXT,
                    description TEXT,
                    download_count INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    reviews INTEGER DEFAULT 0,
                    UNIQUE(name, version)
                );

                CREATE INDEX IF NOT EXISTS idx_models_family ON models(family);
                CREATE INDEX IF NOT EXISTS idx_models_name ON models(name);
                CREATE INDEX IF NOT EXISTS idx_models_tags ON models(tags);
                CREATE INDEX IF NOT EXISTS idx_models_size ON models(size_bytes);

                CREATE TABLE IF NOT EXISTS model_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    location TEXT NOT NULL,
                    installed_at TEXT,
                    last_used TEXT,
                    use_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (model_id) REFERENCES models(id)
                );

                CREATE INDEX IF NOT EXISTS idx_instances_model ON model_instances(model_id);
                CREATE INDEX IF NOT EXISTS idx_instances_location ON model_instances(location);

                CREATE TABLE IF NOT EXISTS model_aliases (
                    alias TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    FOREIGN KEY (model_id) REFERENCES models(id)
                );
            """
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def register(self, metadata: ModelMetadata) -> bool:
        """
        Register a model in the catalog.

        Args:
            metadata: Model metadata

        Returns:
            True if registered successfully
        """
        with self._pool.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO models (
                        id, name, version, family, size_bytes, parameter_count,
                        quantization, context_length, hidden_size, num_layers,
                        source_url, source_repo, sha256, filename_pattern,
                        license, license_url, tags, languages, modalities,
                        benchmark_scores, recommended_use, limitations, training_data,
                        created_at, updated_at, author, organization, description,
                        download_count, rating, reviews
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        metadata.id,
                        metadata.name,
                        metadata.version,
                        metadata.family.value,
                        metadata.size_bytes,
                        metadata.parameter_count,
                        metadata.quantization,
                        metadata.context_length,
                        metadata.hidden_size,
                        metadata.num_layers,
                        metadata.source_url,
                        metadata.source_repo,
                        metadata.sha256,
                        metadata.filename_pattern,
                        metadata.license.value,
                        metadata.license_url,
                        ",".join(metadata.tags),
                        ",".join(metadata.languages),
                        ",".join(m.value if isinstance(m, ModelModality) else m for m in metadata.modalities),
                        json.dumps(metadata.benchmark_scores),
                        metadata.recommended_use,
                        metadata.limitations,
                        metadata.training_data,
                        metadata.created_at.isoformat(),
                        metadata.updated_at.isoformat(),
                        metadata.author,
                        metadata.organization,
                        metadata.description,
                        metadata.download_count,
                        metadata.rating,
                        metadata.reviews,
                    ),
                )
                conn.commit()
                logger.info("model_registered", model_id=metadata.id, name=metadata.name)
                return True
            except sqlite3.Error as e:
                logger.error("model_register_failed", model_id=metadata.id, error=str(e))
                return False

    def get(self, model_id: str) -> ModelMetadata | None:
        """Get model by ID."""
        with self._pool.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,))
            row = cursor.fetchone()

            if not row:
                # Try alias lookup
                alias_row = conn.execute(
                    "SELECT model_id FROM model_aliases WHERE alias = ?",
                    (model_id,),
                ).fetchone()
                if alias_row:
                    cursor = conn.execute(
                        "SELECT * FROM models WHERE id = ?",
                        (alias_row["model_id"],),
                    )
                    row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_metadata(row)

    def get_by_name(self, name: str, version: str | None = None) -> ModelMetadata | None:
        """Get model by name (and optionally version)."""
        with self._pool.get_connection() as conn:
            conn.row_factory = sqlite3.Row

            if version:
                cursor = conn.execute(
                    "SELECT * FROM models WHERE name = ? AND version = ?",
                    (name, version),
                )
            else:
                # Get latest version
                cursor = conn.execute(
                    "SELECT * FROM models WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                    (name,),
                )

            row = cursor.fetchone()
            return self._row_to_metadata(row) if row else None

    def delete(self, model_id: str) -> bool:
        """Delete a model from the registry."""
        with self._pool.get_connection() as conn:
            try:
                conn.execute("DELETE FROM model_instances WHERE model_id = ?", (model_id,))
                conn.execute("DELETE FROM model_aliases WHERE model_id = ?", (model_id,))
                cursor = conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info("model_deleted", model_id=model_id)
                    return True
                return False
            except sqlite3.Error as e:
                logger.error("model_delete_failed", model_id=model_id, error=str(e))
                return False

    def list_all(self, limit: int = 100) -> list[ModelMetadata]:
        """List all models."""
        return self.search(limit=limit)

    # -------------------------------------------------------------------------
    # Search & Discovery
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str | None = None,
        family: ModelFamily | str | None = None,
        tags: list[str] | None = None,
        modalities: list[ModelModality | str] | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        min_context: int | None = None,
        license_type: ModelLicense | str | None = None,
        sort_by: str = "rating",
        limit: int = 50,
    ) -> list[ModelMetadata]:
        """
        Search models by criteria.

        Args:
            query: Text search in name/description
            family: Model family filter
            tags: Required tags (any match)
            modalities: Required modalities
            min_size: Minimum size in bytes
            max_size: Maximum size in bytes
            min_context: Minimum context length
            license_type: License filter
            sort_by: Sort field (rating, downloads, size, name)
            limit: Maximum results

        Returns:
            List of matching models
        """
        with self._pool.get_connection() as conn:
            conn.row_factory = sqlite3.Row

            sql = "SELECT * FROM models WHERE 1=1"
            params: list[Any] = []

            if query:
                sql += " AND (name LIKE ? OR description LIKE ? OR tags LIKE ?)"
                query_pattern = f"%{query}%"
                params.extend([query_pattern, query_pattern, query_pattern])

            if family:
                family_val = family.value if isinstance(family, ModelFamily) else family
                sql += " AND family = ?"
                params.append(family_val)

            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f"%{tag}%")

            if modalities:
                for modality in modalities:
                    mod_val = modality.value if isinstance(modality, ModelModality) else modality
                    sql += " AND modalities LIKE ?"
                    params.append(f"%{mod_val}%")

            if min_size is not None:
                sql += " AND size_bytes >= ?"
                params.append(min_size)

            if max_size is not None:
                sql += " AND size_bytes <= ?"
                params.append(max_size)

            if min_context is not None:
                sql += " AND context_length >= ?"
                params.append(min_context)

            if license_type:
                license_val = license_type.value if isinstance(license_type, ModelLicense) else license_type
                sql += " AND license = ?"
                params.append(license_val)

            # Sorting
            sort_column = {
                "rating": "rating DESC, download_count DESC",
                "downloads": "download_count DESC",
                "size": "size_bytes ASC",
                "name": "name ASC",
                "newest": "created_at DESC",
            }.get(sort_by, "rating DESC")

            sql += f" ORDER BY {sort_column} LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            return [self._row_to_metadata(row) for row in cursor.fetchall()]

    def recommend(
        self,
        task: str,
        constraints: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[ModelMetadata]:
        """
        Recommend models for a specific task.

        Args:
            task: Task type (chat, code, embedding, image, etc.)
            constraints: Optional constraints (max_size_gb, min_rating, etc.)
            limit: Maximum recommendations

        Returns:
            Recommended models sorted by suitability
        """
        constraints = constraints or {}

        # Map task to relevant tags and modalities
        task_config = {
            "chat": {
                "tags": ["chat", "instruct", "assistant", "conversational"],
                "modalities": [ModelModality.TEXT],
            },
            "code": {
                "tags": ["code", "programming", "coding", "developer"],
                "modalities": [ModelModality.CODE, ModelModality.TEXT],
            },
            "embedding": {
                "tags": ["embedding", "retrieval", "semantic", "search"],
                "modalities": [ModelModality.EMBEDDING],
            },
            "image": {
                "tags": ["image", "diffusion", "generation", "art"],
                "modalities": [ModelModality.IMAGE],
            },
            "vision": {
                "tags": ["vision", "multimodal", "image-to-text"],
                "modalities": [ModelModality.MULTIMODAL],
            },
            "audio": {
                "tags": ["audio", "speech", "transcription", "tts"],
                "modalities": [ModelModality.AUDIO],
            },
        }

        config = task_config.get(task.lower(), {"tags": [task], "modalities": []})

        # Apply constraints
        max_size = constraints.get("max_size_gb")
        if max_size:
            max_size = int(max_size * 1024**3)

        min_rating = constraints.get("min_rating", 0.0)
        min_context = constraints.get("min_context")

        # Search with task-specific criteria
        models = self.search(
            tags=config["tags"],
            modalities=config.get("modalities"),
            max_size=max_size,
            min_context=min_context,
            sort_by="rating",
            limit=limit * 2,  # Get more for filtering
        )

        # Filter by rating
        models = [m for m in models if m.rating >= min_rating]

        # Score and sort by relevance
        def score_model(model: ModelMetadata) -> float:
            score = model.rating * 10

            # Bonus for exact tag matches
            for tag in config["tags"]:
                if tag in model.tags:
                    score += 5

            # Prefer smaller models when equal quality
            if model.size_bytes < 5 * 1024**3:  # < 5GB
                score += 2
            elif model.size_bytes < 10 * 1024**3:  # < 10GB
                score += 1

            # Bonus for context length
            if model.context_length:
                if model.context_length >= 32768:
                    score += 3
                elif model.context_length >= 8192:
                    score += 1

            return score

        models.sort(key=score_model, reverse=True)

        return models[:limit]

    def similar(self, model_id: str, limit: int = 5) -> list[ModelMetadata]:
        """
        Find similar models.

        Args:
            model_id: Source model ID
            limit: Maximum results

        Returns:
            List of similar models
        """
        source = self.get(model_id)
        if not source:
            return []

        # Search for models in same family with similar tags
        similar = self.search(
            family=source.family,
            limit=limit + 1,  # +1 to exclude self
        )

        # Exclude source model
        similar = [m for m in similar if m.id != model_id]

        return similar[:limit]

    # -------------------------------------------------------------------------
    # Aliases
    # -------------------------------------------------------------------------

    def add_alias(self, alias: str, model_id: str) -> bool:
        """Add an alias for a model."""
        with self._pool.get_connection() as conn:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO model_aliases (alias, model_id) VALUES (?, ?)",
                    (alias, model_id),
                )
                conn.commit()
                return True
            except sqlite3.Error:
                return False

    def remove_alias(self, alias: str) -> bool:
        """Remove an alias."""
        with self._pool.get_connection() as conn:
            cursor = conn.execute("DELETE FROM model_aliases WHERE alias = ?", (alias,))
            conn.commit()
            return cursor.rowcount > 0

    # -------------------------------------------------------------------------
    # Instance Management
    # -------------------------------------------------------------------------

    def register_instance(
        self,
        model_id: str,
        path: str,
        location: str,
    ) -> int | None:
        """
        Register a model instance (local installation).

        Args:
            model_id: Model ID
            path: File path
            location: Storage location

        Returns:
            Instance ID or None
        """
        with self._pool.get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT OR REPLACE INTO model_instances (
                        model_id, path, location, installed_at
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        model_id,
                        path,
                        location,
                        datetime.utcnow().isoformat(),
                    ),
                )
                conn.commit()
                logger.info(
                    "instance_registered",
                    model_id=model_id,
                    path=path,
                )
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error("instance_register_failed", error=str(e))
                return None

    def get_instances(self, model_id: str) -> list[ModelInstance]:
        """Get all instances of a model."""
        with self._pool.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM model_instances WHERE model_id = ?",
                (model_id,),
            )

            instances = []
            for row in cursor.fetchall():
                instances.append(
                    ModelInstance(
                        id=row["id"],
                        model_id=row["model_id"],
                        path=row["path"],
                        location=row["location"],
                        installed_at=datetime.fromisoformat(row["installed_at"]),
                        last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
                        use_count=row["use_count"],
                        is_active=bool(row["is_active"]),
                    )
                )

            return instances

    def record_usage(self, instance_id: int):
        """Record model instance usage."""
        with self._pool.get_connection() as conn:
            conn.execute(
                """
                UPDATE model_instances
                SET last_used = ?, use_count = use_count + 1
                WHERE id = ?
            """,
                (datetime.utcnow().isoformat(), instance_id),
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        with self._pool.get_connection() as conn:
            stats = {}

            # Total models
            stats["total_models"] = conn.execute(
                "SELECT COUNT(*) FROM models"
            ).fetchone()[0]

            # By family
            cursor = conn.execute(
                "SELECT family, COUNT(*) as count FROM models GROUP BY family"
            )
            stats["by_family"] = {row[0]: row[1] for row in cursor.fetchall()}

            # Total size
            stats["total_size_bytes"] = conn.execute(
                "SELECT SUM(size_bytes) FROM models"
            ).fetchone()[0] or 0

            # Instances
            stats["total_instances"] = conn.execute(
                "SELECT COUNT(*) FROM model_instances"
            ).fetchone()[0]

            return stats

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _row_to_metadata(self, row: sqlite3.Row) -> ModelMetadata:
        """Convert database row to ModelMetadata."""
        return ModelMetadata(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            family=ModelFamily(row["family"]),
            size_bytes=row["size_bytes"],
            parameter_count=row["parameter_count"],
            quantization=row["quantization"],
            context_length=row["context_length"],
            hidden_size=row["hidden_size"],
            num_layers=row["num_layers"],
            source_url=row["source_url"] or "",
            source_repo=row["source_repo"] or "",
            sha256=row["sha256"] or "",
            filename_pattern=row["filename_pattern"] or "",
            license=ModelLicense(row["license"]),
            license_url=row["license_url"] or "",
            tags=row["tags"].split(",") if row["tags"] else [],
            languages=row["languages"].split(",") if row["languages"] else [],
            modalities=[ModelModality(m) for m in row["modalities"].split(",") if m and m in ModelModality._value2member_map_] if row["modalities"] else [],
            benchmark_scores=json.loads(row["benchmark_scores"]) if row["benchmark_scores"] else {},
            recommended_use=row["recommended_use"] or "",
            limitations=row["limitations"] or "",
            training_data=row["training_data"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            author=row["author"] or "",
            organization=row["organization"] or "",
            description=row["description"] or "",
            download_count=row["download_count"],
            rating=row["rating"],
            reviews=row["reviews"],
        )

    def seed(self, models: list[ModelMetadata] | None = None):
        """Seed registry with known models."""
        models = models or KNOWN_MODELS
        for model in models:
            self.register(model)
        logger.info("registry_seeded", count=len(models))


# =============================================================================
# Known Models Seed Data
# =============================================================================

KNOWN_MODELS: list[ModelMetadata] = [
    # Llama Family
    ModelMetadata(
        id="llama-3.2-1b-instruct",
        name="Llama 3.2 1B Instruct",
        version="3.2",
        family=ModelFamily.LLAMA,
        size_bytes=1_300_000_000,
        parameter_count=1_000_000_000,
        context_length=8192,
        source_url="https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct",
        source_repo="meta-llama/Llama-3.2-1B-Instruct",
        license=ModelLicense.LLAMA,
        tags=["chat", "instruct", "assistant", "lightweight"],
        languages=["en"],
        modalities=[ModelModality.TEXT],
        recommended_use="Edge deployment, mobile, fast inference",
        organization="Meta",
        description="Ultra-lightweight instruction-tuned model for resource-constrained environments",
        rating=4.0,
    ),
    ModelMetadata(
        id="llama-3.2-3b-instruct",
        name="Llama 3.2 3B Instruct",
        version="3.2",
        family=ModelFamily.LLAMA,
        size_bytes=2_000_000_000,
        parameter_count=3_000_000_000,
        context_length=8192,
        source_url="https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
        source_repo="meta-llama/Llama-3.2-3B-Instruct",
        license=ModelLicense.LLAMA,
        tags=["chat", "instruct", "assistant"],
        languages=["en"],
        modalities=[ModelModality.TEXT],
        recommended_use="General purpose chat and assistance",
        organization="Meta",
        description="Lightweight instruction-tuned model from Llama 3.2 series",
        rating=4.5,
    ),
    ModelMetadata(
        id="llama-3.1-8b-instruct",
        name="Llama 3.1 8B Instruct",
        version="3.1",
        family=ModelFamily.LLAMA,
        size_bytes=5_000_000_000,
        parameter_count=8_000_000_000,
        context_length=131072,
        source_url="https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
        source_repo="meta-llama/Llama-3.1-8B-Instruct",
        license=ModelLicense.LLAMA,
        tags=["chat", "instruct", "assistant", "long-context"],
        languages=["en", "de", "fr", "it", "pt", "hi", "es", "th"],
        modalities=[ModelModality.TEXT],
        recommended_use="General chat with extended context support",
        organization="Meta",
        description="Mid-size model with 128K context window",
        rating=4.7,
    ),
    # Mistral Family
    ModelMetadata(
        id="mistral-7b-instruct-v0.3",
        name="Mistral 7B Instruct v0.3",
        version="0.3",
        family=ModelFamily.MISTRAL,
        size_bytes=4_400_000_000,
        parameter_count=7_000_000_000,
        context_length=32768,
        source_url="https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3",
        source_repo="mistralai/Mistral-7B-Instruct-v0.3",
        license=ModelLicense.APACHE_2,
        tags=["chat", "instruct", "efficient"],
        languages=["en"],
        modalities=[ModelModality.TEXT],
        recommended_use="Efficient instruction following",
        organization="Mistral AI",
        description="Highly efficient instruction-tuned model with sliding window attention",
        rating=4.6,
    ),
    # Qwen Family
    ModelMetadata(
        id="qwen2.5-7b-instruct",
        name="Qwen 2.5 7B Instruct",
        version="2.5",
        family=ModelFamily.QWEN,
        size_bytes=4_700_000_000,
        parameter_count=7_000_000_000,
        context_length=131072,
        source_url="https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        source_repo="Qwen/Qwen2.5-7B-Instruct",
        license=ModelLicense.QWEN,
        tags=["chat", "instruct", "multilingual", "coding"],
        languages=["en", "zh"],
        modalities=[ModelModality.TEXT, ModelModality.CODE],
        recommended_use="Multilingual chat and coding assistance",
        organization="Alibaba",
        description="Strong multilingual model with coding capabilities",
        rating=4.6,
    ),
    # Embedding Models
    ModelMetadata(
        id="nomic-embed-text-v1.5",
        name="Nomic Embed Text v1.5",
        version="1.5",
        family=ModelFamily.NOMIC,
        size_bytes=550_000_000,
        parameter_count=137_000_000,
        context_length=8192,
        source_url="https://huggingface.co/nomic-ai/nomic-embed-text-v1.5",
        source_repo="nomic-ai/nomic-embed-text-v1.5",
        license=ModelLicense.APACHE_2,
        tags=["embedding", "retrieval", "semantic-search", "rag"],
        languages=["en"],
        modalities=[ModelModality.EMBEDDING],
        recommended_use="RAG pipelines, semantic search, document retrieval",
        organization="Nomic AI",
        description="High-quality text embedding model with 8K context",
        rating=4.8,
    ),
    # Code Models
    ModelMetadata(
        id="deepseek-coder-6.7b-instruct",
        name="DeepSeek Coder 6.7B Instruct",
        version="1.0",
        family=ModelFamily.DEEPSEEK,
        size_bytes=4_200_000_000,
        parameter_count=6_700_000_000,
        context_length=16384,
        source_url="https://huggingface.co/deepseek-ai/deepseek-coder-6.7b-instruct",
        source_repo="deepseek-ai/deepseek-coder-6.7b-instruct",
        license=ModelLicense.MIT,
        tags=["code", "programming", "developer", "instruct"],
        languages=["en"],
        modalities=[ModelModality.CODE],
        recommended_use="Code generation, completion, and explanation",
        organization="DeepSeek",
        description="Specialized coding model trained on 2T tokens of code",
        rating=4.5,
    ),
    # Phi Family
    ModelMetadata(
        id="phi-3-mini-4k-instruct",
        name="Phi-3 Mini 4K Instruct",
        version="3.0",
        family=ModelFamily.PHI,
        size_bytes=2_400_000_000,
        parameter_count=3_800_000_000,
        context_length=4096,
        source_url="https://huggingface.co/microsoft/Phi-3-mini-4k-instruct",
        source_repo="microsoft/Phi-3-mini-4k-instruct",
        license=ModelLicense.MIT,
        tags=["chat", "instruct", "efficient", "lightweight"],
        languages=["en"],
        modalities=[ModelModality.TEXT],
        recommended_use="Resource-efficient inference with strong reasoning",
        organization="Microsoft",
        description="Compact model with impressive reasoning capabilities",
        rating=4.4,
    ),
    # Gemma Family
    ModelMetadata(
        id="gemma-2-9b-it",
        name="Gemma 2 9B Instruct",
        version="2.0",
        family=ModelFamily.GEMMA,
        size_bytes=5_700_000_000,
        parameter_count=9_000_000_000,
        context_length=8192,
        source_url="https://huggingface.co/google/gemma-2-9b-it",
        source_repo="google/gemma-2-9b-it",
        license=ModelLicense.GEMMA,
        tags=["chat", "instruct", "reasoning"],
        languages=["en"],
        modalities=[ModelModality.TEXT],
        recommended_use="High-quality instruction following and reasoning",
        organization="Google",
        description="Google's open model with strong instruction following",
        rating=4.5,
    ),
]
