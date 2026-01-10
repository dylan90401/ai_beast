from modules.core.events import EventBus


def test_event_bus_emits():
    bus = EventBus()
    seen = []

    def handler(payload):
        seen.append(payload.get("value"))

    bus.on("ping", handler)
    bus.emit("ping", {"value": 123})
    assert seen == [123]
