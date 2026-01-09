"""
Model registry and catalog module.

Provides centralized model metadata management, search, and recommendations.
"""

from modules.registry.catalog import (
    ModelFamily,
    ModelLicense,
    ModelMetadata,
    ModelRegistry,
    KNOWN_MODELS,
)

__all__ = [
    "ModelFamily",
    "ModelLicense",
    "ModelMetadata",
    "ModelRegistry",
    "KNOWN_MODELS",
]
