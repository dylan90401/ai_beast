from modules.core.events import EventBus


def test_event_bus_publish():
    bus = EventBus()
    seen = []

    def handler(payload):
        seen.append(payload["value"])

    bus.subscribe("test", handler)
    bus.publish("test", {"value": 7})
    assert seen == [7]
