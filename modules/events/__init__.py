"""
Event-driven architecture module.

Provides pub/sub event bus for decoupled communication between components.
"""

from modules.events.bus import (
    Event,
    EventBus,
    EventHandler,
    EventPriority,
    get_event_bus,
    subscribe,
    publish,
    emit,
)

__all__ = [
    "Event",
    "EventBus",
    "EventHandler",
    "EventPriority",
    "get_event_bus",
    "subscribe",
    "publish",
    "emit",
]
