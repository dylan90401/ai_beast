"""
Model versioning and rollback system.

Provides snapshot-based versioning for models with automatic hash-based
version identification and rollback capabilities.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ModelSnapshot:
    """Model version snapshot."""

    model_name: str
    version: str
    path: Path
    sha256: str
    size_bytes: int
    created_at: datetime
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "version": self.version,
            "path": str(self.path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "tags": self.tags,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelSnapshot:
        """Create from dictionary."""
        return cls(
            model_name=data["model_name"],
            version=data["version"],
            path=Path(data["path"]),
            sha256=data["sha256"],
            size_bytes=data["size_bytes"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            description=data.get("description", ""),
        )

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
    def short_version(self) -> str:
        """Short version string (first 8 chars of hash)."""
        return self.version[:8]


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    model_name: str
    from_version: str | None
    to_version: str
    backup_created: bool
    message: str


# =============================================================================
# Version Manager
# =============================================================================


class VersionManager:
    """
    Manages model versions and rollback operations.

    Provides:
    - Automatic snapshot creation with hash-based versioning
    - Version listing and comparison
    - Rollback to any previous version
    - Automatic cleanup of old versions
    """

    def __init__(self, snapshots_dir: Path | str | None = None):
        """
        Initialize version manager.

        Args:
            snapshots_dir: Directory for storing snapshots
        """
        if snapshots_dir is None:
            from modules.container import get_container

            container = get_container()
            context = container.get("context")
            if context:
                snapshots_dir = Path(context.data_dir) / "versions"
            else:
                snapshots_dir = Path("data/versions")

        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Snapshot Operations
    # -------------------------------------------------------------------------

    def create_snapshot(
        self,
        model_path: Path,
        metadata: dict | None = None,
        tags: list[str] | None = None,
        description: str = "",
        force: bool = False,
    ) -> ModelSnapshot:
        """
        Create a versioned snapshot of a model.

        Args:
            model_path: Path to model file
            metadata: Optional metadata to store
            tags: Optional tags for the snapshot
            description: Optional description
            force: Create even if identical version exists

        Returns:
            ModelSnapshot instance

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Compute hash for version identification
        sha256 = self._compute_hash(model_path)
        version = sha256

        # Create model-specific snapshot directory
        model_name = model_path.stem
        snapshot_dir = self.snapshots_dir / model_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Build snapshot path
        snapshot_path = snapshot_dir / f"{model_name}_{version[:8]}{model_path.suffix}"

        # Check if identical snapshot already exists
        if snapshot_path.exists() and not force:
            existing = self._load_metadata(snapshot_path)
            if existing and existing.sha256 == sha256:
                logger.info(
                    "snapshot_exists",
                    model=model_name,
                    version=version[:8],
                )
                return existing

        # Copy file
        file_size = model_path.stat().st_size
        logger.info(
            "creating_snapshot",
            model=model_name,
            version=version[:8],
            size_mb=file_size / (1024**2),
        )

        shutil.copy2(model_path, snapshot_path)

        # Create snapshot object
        snapshot = ModelSnapshot(
            model_name=model_name,
            version=version,
            path=snapshot_path,
            sha256=sha256,
            size_bytes=file_size,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
            tags=tags or [],
            description=description,
        )

        # Save metadata
        self._save_metadata(snapshot)

        logger.info(
            "snapshot_created",
            model=snapshot.model_name,
            version=version[:8],
            path=str(snapshot_path),
        )

        return snapshot

    def list_snapshots(
        self,
        model_name: str | None = None,
        tags: list[str] | None = None,
    ) -> list[ModelSnapshot]:
        """
        List all snapshots.

        Args:
            model_name: Optional filter by model name
            tags: Optional filter by tags (any match)

        Returns:
            List of snapshots, sorted by creation time (newest first)
        """
        snapshots: list[ModelSnapshot] = []

        # Determine directories to scan
        if model_name:
            dirs = [self.snapshots_dir / model_name]
        else:
            dirs = [d for d in self.snapshots_dir.iterdir() if d.is_dir()]

        for snapshot_dir in dirs:
            if not snapshot_dir.exists():
                continue

            # Find all metadata files
            for metadata_file in snapshot_dir.glob("*.json"):
                snapshot = self._load_metadata_from_file(metadata_file)
                if snapshot:
                    # Apply tag filter
                    if tags:
                        if not any(t in snapshot.tags for t in tags):
                            continue
                    snapshots.append(snapshot)

        # Sort by creation time (newest first)
        snapshots.sort(key=lambda s: s.created_at, reverse=True)

        return snapshots

    def get_snapshot(self, model_name: str, version: str) -> ModelSnapshot | None:
        """
        Get specific snapshot.

        Args:
            model_name: Model name
            version: Version ID (can be short or full hash)

        Returns:
            ModelSnapshot or None if not found
        """
        snapshots = self.list_snapshots(model_name)
        for snapshot in snapshots:
            # Match full or short version
            if snapshot.version.startswith(version) or snapshot.version == version:
                return snapshot
        return None

    def get_latest(self, model_name: str) -> ModelSnapshot | None:
        """Get the latest snapshot for a model."""
        snapshots = self.list_snapshots(model_name)
        return snapshots[0] if snapshots else None

    # -------------------------------------------------------------------------
    # Rollback Operations
    # -------------------------------------------------------------------------

    def rollback(
        self,
        model_name: str,
        target_version: str,
        destination: Path,
        create_backup: bool = True,
    ) -> RollbackResult:
        """
        Rollback model to a previous version.

        Args:
            model_name: Model name
            target_version: Target version to rollback to
            destination: Destination path for rollback
            create_backup: Create backup of current version first

        Returns:
            RollbackResult with operation details
        """
        destination = Path(destination)
        backup_created = False
        current_version = None

        # Find target snapshot
        snapshot = self.get_snapshot(model_name, target_version)
        if not snapshot:
            logger.error(
                "snapshot_not_found",
                model=model_name,
                version=target_version,
            )
            return RollbackResult(
                success=False,
                model_name=model_name,
                from_version=None,
                to_version=target_version,
                backup_created=False,
                message=f"Snapshot not found: {target_version}",
            )

        try:
            # Create backup of current file if it exists
            if destination.exists() and create_backup:
                current_snapshot = self.create_snapshot(
                    destination,
                    metadata={"rollback_backup": True, "rollback_to": target_version},
                    tags=["backup", "pre-rollback"],
                    description=f"Automatic backup before rollback to {target_version[:8]}",
                )
                current_version = current_snapshot.version[:8]
                backup_created = True
                logger.info(
                    "backup_created",
                    model=model_name,
                    version=current_version,
                )

            # Perform rollback
            logger.info(
                "rolling_back",
                model=model_name,
                from_version=current_version or "none",
                to_version=snapshot.version[:8],
            )

            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy snapshot to destination
            shutil.copy2(snapshot.path, destination)

            logger.info(
                "rollback_complete",
                model=model_name,
                version=snapshot.version[:8],
                path=str(destination),
            )

            return RollbackResult(
                success=True,
                model_name=model_name,
                from_version=current_version,
                to_version=snapshot.version[:8],
                backup_created=backup_created,
                message=f"Successfully rolled back to version {snapshot.version[:8]}",
            )

        except Exception as e:
            logger.exception(
                "rollback_failed",
                model=model_name,
                version=target_version,
            )
            return RollbackResult(
                success=False,
                model_name=model_name,
                from_version=current_version,
                to_version=target_version,
                backup_created=backup_created,
                message=f"Rollback failed: {str(e)}",
            )

    # -------------------------------------------------------------------------
    # Comparison Operations
    # -------------------------------------------------------------------------

    def compare(
        self,
        model_name: str,
        version_a: str,
        version_b: str,
    ) -> dict[str, Any]:
        """
        Compare two snapshots.

        Args:
            model_name: Model name
            version_a: First version
            version_b: Second version

        Returns:
            Comparison result dict
        """
        snap_a = self.get_snapshot(model_name, version_a)
        snap_b = self.get_snapshot(model_name, version_b)

        if not snap_a or not snap_b:
            return {
                "error": "One or both snapshots not found",
                "found_a": snap_a is not None,
                "found_b": snap_b is not None,
            }

        return {
            "model_name": model_name,
            "version_a": {
                "version": snap_a.version[:8],
                "created_at": snap_a.created_at.isoformat(),
                "size_bytes": snap_a.size_bytes,
                "tags": snap_a.tags,
            },
            "version_b": {
                "version": snap_b.version[:8],
                "created_at": snap_b.created_at.isoformat(),
                "size_bytes": snap_b.size_bytes,
                "tags": snap_b.tags,
            },
            "identical": snap_a.sha256 == snap_b.sha256,
            "size_diff": snap_b.size_bytes - snap_a.size_bytes,
            "time_diff_seconds": (snap_b.created_at - snap_a.created_at).total_seconds(),
        }

    # -------------------------------------------------------------------------
    # Cleanup Operations
    # -------------------------------------------------------------------------

    def delete_snapshot(self, model_name: str, version: str) -> bool:
        """
        Delete a snapshot.

        Args:
            model_name: Model name
            version: Version to delete

        Returns:
            True if deleted successfully
        """
        snapshot = self.get_snapshot(model_name, version)
        if not snapshot:
            return False

        try:
            # Delete model file
            if snapshot.path.exists():
                snapshot.path.unlink()

            # Delete metadata file
            metadata_file = snapshot.path.with_suffix(".json")
            if metadata_file.exists():
                metadata_file.unlink()

            logger.info(
                "snapshot_deleted",
                model=model_name,
                version=version[:8],
            )
            return True

        except Exception as e:
            logger.error(
                "snapshot_delete_failed",
                model=model_name,
                version=version,
                error=str(e),
            )
            return False

    def cleanup(
        self,
        model_name: str | None = None,
        keep_count: int = 5,
        keep_tagged: bool = True,
        older_than_days: int | None = None,
    ) -> dict[str, int]:
        """
        Clean up old snapshots.

        Args:
            model_name: Specific model to clean (None for all)
            keep_count: Number of recent snapshots to keep
            keep_tagged: Keep snapshots with tags
            older_than_days: Only delete snapshots older than this

        Returns:
            Dict with deleted counts per model
        """
        results: dict[str, int] = {}
        cutoff_date = None
        if older_than_days:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        # Get models to process
        if model_name:
            models = [model_name]
        else:
            models = [d.name for d in self.snapshots_dir.iterdir() if d.is_dir()]

        for model in models:
            snapshots = self.list_snapshots(model)

            if len(snapshots) <= keep_count:
                results[model] = 0
                continue

            # Determine which to delete
            to_keep = snapshots[:keep_count]
            to_delete = snapshots[keep_count:]

            deleted = 0
            for snapshot in to_delete:
                # Skip tagged snapshots if requested
                if keep_tagged and snapshot.tags:
                    continue

                # Skip if not old enough
                if cutoff_date and snapshot.created_at > cutoff_date:
                    continue

                if self.delete_snapshot(model, snapshot.version):
                    deleted += 1

            results[model] = deleted
            if deleted > 0:
                logger.info(
                    "snapshots_cleaned",
                    model=model,
                    deleted=deleted,
                    kept=len(to_keep),
                )

        return results

    def get_storage_usage(self, model_name: str | None = None) -> dict[str, Any]:
        """
        Get storage usage statistics.

        Args:
            model_name: Specific model or None for all

        Returns:
            Storage statistics dict
        """
        snapshots = self.list_snapshots(model_name)

        total_bytes = sum(s.size_bytes for s in snapshots)
        by_model: dict[str, int] = {}

        for s in snapshots:
            by_model[s.model_name] = by_model.get(s.model_name, 0) + s.size_bytes

        return {
            "total_snapshots": len(snapshots),
            "total_bytes": total_bytes,
            "total_human": f"{total_bytes / (1024**3):.2f} GB",
            "by_model": by_model,
            "models_count": len(by_model),
        }

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _compute_hash(self, path: Path, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _save_metadata(self, snapshot: ModelSnapshot):
        """Save snapshot metadata to JSON file."""
        metadata_file = snapshot.path.with_suffix(".json")
        metadata_file.write_text(json.dumps(snapshot.to_dict(), indent=2))

    def _load_metadata(self, snapshot_path: Path) -> ModelSnapshot | None:
        """Load snapshot metadata from corresponding JSON file."""
        metadata_file = snapshot_path.with_suffix(".json")
        return self._load_metadata_from_file(metadata_file)

    def _load_metadata_from_file(self, metadata_file: Path) -> ModelSnapshot | None:
        """Load snapshot from metadata JSON file."""
        if not metadata_file.exists():
            return None

        try:
            data = json.loads(metadata_file.read_text())
            return ModelSnapshot.from_dict(data)
        except Exception as e:
            logger.error(
                "metadata_load_failed",
                path=str(metadata_file),
                error=str(e),
            )
            return None


# =============================================================================
# Convenience Functions
# =============================================================================


def get_version_manager() -> VersionManager:
    """Get the global version manager instance."""
    from modules.container import get_container

    container = get_container()
    manager = container.get("version_manager")
    if not manager:
        manager = VersionManager()
        container.register("version_manager", manager)
    return manager
