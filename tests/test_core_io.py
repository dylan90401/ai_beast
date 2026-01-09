import asyncio

from modules.core.io import read_text, write_text


def test_async_io(tmp_path):
    target = tmp_path / "data.txt"
    asyncio.run(write_text(target, "hello"))
    data = asyncio.run(read_text(target))
    assert data == "hello"
