import os
import urllib.request

import pytest


def _request_ok(url: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-beast-it"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return 200 <= resp.status < 400


@pytest.mark.integration
def test_qdrant_reachable():
    base = os.environ.get("AI_BEAST_BIND_ADDR", "127.0.0.1")
    port = os.environ.get("PORT_QDRANT", "6333")
    assert _request_ok(f"http://{base}:{port}/readyz")


@pytest.mark.integration
def test_open_webui_reachable():
    base = os.environ.get("AI_BEAST_BIND_ADDR", "127.0.0.1")
    port = os.environ.get("PORT_WEBUI", "3000")
    assert _request_ok(f"http://{base}:{port}/health")
