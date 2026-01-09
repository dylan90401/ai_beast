"""
Async file helpers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


async def read_text(path: Path, encoding: str = "utf-8") -> str:
    return await asyncio.to_thread(Path(path).read_text, encoding=encoding)


async def write_text(path: Path, data: str, encoding: str = "utf-8") -> None:
    await asyncio.to_thread(Path(path).write_text, data, encoding)
