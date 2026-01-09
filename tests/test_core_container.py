from modules.core.container import Container


def test_container_singleton():
    container = Container()
    container.register("value", lambda: {"ok": True})
    a = container.get("value")
    b = container.get("value")
    assert a is b
    assert a["ok"]
