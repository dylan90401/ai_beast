"""
Event bus for pub/sub event-driven architecture.

Provides:
- Synchronous and asynchronous event handling
- Event prioritization
- Wildcard subscriptions
- Event history and replay
- Dead letter handling
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Awaitable, Callable, TypeVar

from modules.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Types & Enums
# =============================================================================


class EventPriority(IntEnum):
    """Event handler priority (lower = higher priority)."""

    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 90
    BACKGROUND = 100


# Handler type: can be sync or async function
EventHandler = Callable[["Event"], Any] | Callable[["Event"], Awaitable[Any]]

T = TypeVar("T")


# =============================================================================
# Event Data Class
# =============================================================================


@dataclass
class Event:
    """
    Event object containing event data and metadata.

    Attributes:
        type: Event type (e.g., "model.downloaded", "rag.ingested")
        data: Event payload data
        id: Unique event ID
        timestamp: When the event was created
        source: Event source identifier
        metadata: Additional metadata
        propagate: Whether to continue to other handlers
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    propagate: bool = True

    def stop_propagation(self):
        """Stop event from propagating to other handlers."""
        self.propagate = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "data": self.data,
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Create from dictionary."""
        return cls(
            type=data["type"],
            data=data.get("data", {}),
            id=data.get("id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Subscription:
    """Event subscription."""

    handler: EventHandler
    pattern: str
    priority: EventPriority
    is_async: bool
    once: bool = False
    filter_fn: Callable[[Event], bool] | None = None


# =============================================================================
# Event Bus
# =============================================================================


class EventBus:
    """
    Central event bus for pub/sub communication.

    Features:
    - Pattern-based subscriptions (wildcards with *)
    - Priority-ordered handler execution
    - Async and sync handler support
    - Event history with replay capability
    - Dead letter queue for failed events
    """

    def __init__(
        self,
        max_history: int = 1000,
        enable_dead_letter: bool = True,
    ):
        """
        Initialize event bus.

        Args:
            max_history: Maximum events to keep in history
            enable_dead_letter: Enable dead letter queue for failed handlers
        """
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._pattern_cache: dict[str, re.Pattern] = {}
        self._history: list[Event] = []
        self._max_history = max_history
        self._dead_letter: list[tuple[Event, Exception]] = []
        self._enable_dead_letter = enable_dead_letter
        self._middleware: list[Callable[[Event], Event | None]] = []

    # -------------------------------------------------------------------------
    # Subscription
    # -------------------------------------------------------------------------

    def subscribe(
        self,
        pattern: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> Callable[[], None]:
        """
        Subscribe to events matching a pattern.

        Args:
            pattern: Event type pattern (supports * wildcard)
            handler: Handler function (sync or async)
            priority: Handler priority
            once: Unsubscribe after first event
            filter_fn: Optional filter function

        Returns:
            Unsubscribe function

        Examples:
            bus.subscribe("model.downloaded", handler)
            bus.subscribe("model.*", handler)
            bus.subscribe("*.error", error_handler)
        """
        is_async = asyncio.iscoroutinefunction(handler)

        subscription = Subscription(
            handler=handler,
            pattern=pattern,
            priority=priority,
            is_async=is_async,
            once=once,
            filter_fn=filter_fn,
        )

        # Add and sort by priority
        self._subscriptions[pattern].append(subscription)
        self._subscriptions[pattern].sort(key=lambda s: s.priority)

        # Cache compiled pattern
        if pattern not in self._pattern_cache:
            regex_pattern = pattern.replace(".", r"\.").replace("*", r"[^.]*")
            self._pattern_cache[pattern] = re.compile(f"^{regex_pattern}$")

        logger.debug(
            "event_subscribed",
            pattern=pattern,
            handler=handler.__name__,
            priority=priority.name,
        )

        # Return unsubscribe function
        def unsubscribe():
            if subscription in self._subscriptions[pattern]:
                self._subscriptions[pattern].remove(subscription)
                logger.debug("event_unsubscribed", pattern=pattern)

        return unsubscribe

    def unsubscribe_all(self, pattern: str | None = None):
        """
        Unsubscribe all handlers.

        Args:
            pattern: Specific pattern to unsubscribe, or None for all
        """
        if pattern:
            self._subscriptions[pattern].clear()
        else:
            self._subscriptions.clear()

    # -------------------------------------------------------------------------
    # Publishing
    # -------------------------------------------------------------------------

    def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        source: str = "",
        **kwargs,
    ) -> Event:
        """
        Publish an event synchronously.

        Args:
            event_type: Event type
            data: Event data
            source: Event source
            **kwargs: Additional data fields

        Returns:
            The published event
        """
        event = Event(
            type=event_type,
            data={**(data or {}), **kwargs},
            source=source,
        )

        return self._dispatch_sync(event)

    async def publish_async(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        source: str = "",
        **kwargs,
    ) -> Event:
        """
        Publish an event asynchronously.

        Args:
            event_type: Event type
            data: Event data
            source: Event source
            **kwargs: Additional data fields

        Returns:
            The published event
        """
        event = Event(
            type=event_type,
            data={**(data or {}), **kwargs},
            source=source,
        )

        return await self._dispatch_async(event)

    def emit(self, event: Event) -> Event:
        """
        Emit a pre-constructed event synchronously.

        Args:
            event: Event to emit

        Returns:
            The emitted event
        """
        return self._dispatch_sync(event)

    async def emit_async(self, event: Event) -> Event:
        """
        Emit a pre-constructed event asynchronously.

        Args:
            event: Event to emit

        Returns:
            The emitted event
        """
        return await self._dispatch_async(event)

    # -------------------------------------------------------------------------
    # Middleware
    # -------------------------------------------------------------------------

    def use(self, middleware: Callable[[Event], Event | None]):
        """
        Add middleware to process events before dispatch.

        Middleware can modify events or return None to cancel.

        Args:
            middleware: Middleware function
        """
        self._middleware.append(middleware)

    def _apply_middleware(self, event: Event) -> Event | None:
        """Apply all middleware to event."""
        for mw in self._middleware:
            event = mw(event)
            if event is None:
                return None
        return event

    # -------------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------------

    def _get_matching_subscriptions(self, event_type: str) -> list[Subscription]:
        """Get all subscriptions matching an event type."""
        matching: list[Subscription] = []

        for pattern, subs in self._subscriptions.items():
            regex = self._pattern_cache.get(pattern)
            if regex and regex.match(event_type):
                matching.extend(subs)

        # Sort by priority
        matching.sort(key=lambda s: s.priority)
        return matching

    def _dispatch_sync(self, event: Event) -> Event:
        """Dispatch event to handlers synchronously."""
        # Apply middleware
        event = self._apply_middleware(event)
        if event is None:
            return event

        # Add to history
        self._add_to_history(event)

        logger.debug(
            "event_dispatching",
            type=event.type,
            id=event.id,
        )

        # Get matching subscriptions
        subscriptions = self._get_matching_subscriptions(event.type)
        to_remove: list[tuple[str, Subscription]] = []

        for sub in subscriptions:
            if not event.propagate:
                break

            # Apply filter
            if sub.filter_fn and not sub.filter_fn(event):
                continue

            try:
                if sub.is_async:
                    # Run async handler in event loop
                    asyncio.get_event_loop().run_until_complete(sub.handler(event))
                else:
                    sub.handler(event)

                if sub.once:
                    to_remove.append((sub.pattern, sub))

            except Exception as e:
                logger.exception(
                    "event_handler_error",
                    type=event.type,
                    handler=sub.handler.__name__,
                )
                if self._enable_dead_letter:
                    self._dead_letter.append((event, e))

        # Remove one-time handlers
        for pattern, sub in to_remove:
            if sub in self._subscriptions[pattern]:
                self._subscriptions[pattern].remove(sub)

        logger.debug("event_dispatched", type=event.type, id=event.id)
        return event

    async def _dispatch_async(self, event: Event) -> Event:
        """Dispatch event to handlers asynchronously."""
        # Apply middleware
        event = self._apply_middleware(event)
        if event is None:
            return event

        # Add to history
        self._add_to_history(event)

        logger.debug(
            "event_dispatching_async",
            type=event.type,
            id=event.id,
        )

        # Get matching subscriptions
        subscriptions = self._get_matching_subscriptions(event.type)
        to_remove: list[tuple[str, Subscription]] = []

        for sub in subscriptions:
            if not event.propagate:
                break

            # Apply filter
            if sub.filter_fn and not sub.filter_fn(event):
                continue

            try:
                if sub.is_async:
                    await sub.handler(event)
                else:
                    sub.handler(event)

                if sub.once:
                    to_remove.append((sub.pattern, sub))

            except Exception as e:
                logger.exception(
                    "event_handler_error",
                    type=event.type,
                    handler=sub.handler.__name__,
                )
                if self._enable_dead_letter:
                    self._dead_letter.append((event, e))

        # Remove one-time handlers
        for pattern, sub in to_remove:
            if sub in self._subscriptions[pattern]:
                self._subscriptions[pattern].remove(sub)

        logger.debug("event_dispatched_async", type=event.type, id=event.id)
        return event

    # -------------------------------------------------------------------------
    # History & Replay
    # -------------------------------------------------------------------------

    def _add_to_history(self, event: Event):
        """Add event to history."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(
        self,
        event_type: str | None = None,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[Event]:
        """
        Get event history.

        Args:
            event_type: Filter by event type
            limit: Maximum events to return
            since: Only events after this time

        Returns:
            List of events (newest first)
        """
        events = self._history.copy()

        if event_type:
            pattern = event_type.replace(".", r"\.").replace("*", r"[^.]*")
            regex = re.compile(f"^{pattern}$")
            events = [e for e in events if regex.match(e.type)]

        if since:
            events = [e for e in events if e.timestamp > since]

        return list(reversed(events))[:limit]

    def replay(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """
        Replay historical events.

        Args:
            event_type: Filter by event type
            since: Only events after this time

        Returns:
            Number of events replayed
        """
        events = self.get_history(event_type, limit=self._max_history, since=since)
        events.reverse()  # Replay in original order

        for event in events:
            self.emit(event)

        logger.info("events_replayed", count=len(events))
        return len(events)

    # -------------------------------------------------------------------------
    # Dead Letter Queue
    # -------------------------------------------------------------------------

    def get_dead_letters(self, limit: int = 100) -> list[tuple[Event, str]]:
        """Get failed events from dead letter queue."""
        return [
            (event, str(error))
            for event, error in self._dead_letter[-limit:]
        ]

    def retry_dead_letters(self) -> int:
        """Retry all events in dead letter queue."""
        to_retry = self._dead_letter.copy()
        self._dead_letter.clear()

        for event, _ in to_retry:
            self.emit(event)

        return len(to_retry)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        total_subs = sum(len(subs) for subs in self._subscriptions.values())

        return {
            "patterns": len(self._subscriptions),
            "total_subscriptions": total_subs,
            "history_size": len(self._history),
            "dead_letters": len(self._dead_letter),
            "middleware_count": len(self._middleware),
        }


# =============================================================================
# Global Instance
# =============================================================================

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# =============================================================================
# Convenience Functions
# =============================================================================


def subscribe(
    pattern: str,
    handler: EventHandler | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    once: bool = False,
):
    """
    Subscribe to events (can be used as decorator).

    Usage:
        @subscribe("model.downloaded")
        def on_download(event):
            ...

        # Or:
        subscribe("model.*", handler)
    """
    bus = get_event_bus()

    if handler is not None:
        return bus.subscribe(pattern, handler, priority, once)

    # Decorator usage
    def decorator(fn: EventHandler):
        bus.subscribe(pattern, fn, priority, once)
        return fn

    return decorator


def publish(
    event_type: str,
    data: dict[str, Any] | None = None,
    source: str = "",
    **kwargs,
) -> Event:
    """Publish an event."""
    return get_event_bus().publish(event_type, data, source, **kwargs)


def emit(event: Event) -> Event:
    """Emit a pre-constructed event."""
    return get_event_bus().emit(event)


# =============================================================================
# Standard Event Types
# =============================================================================

class EventTypes:
    """Standard event type constants."""

    # Model events
    MODEL_DOWNLOADED = "model.downloaded"
    MODEL_DELETED = "model.deleted"
    MODEL_LOADED = "model.loaded"
    MODEL_UNLOADED = "model.unloaded"
    MODEL_ERROR = "model.error"

    # RAG events
    RAG_INGESTED = "rag.ingested"
    RAG_QUERIED = "rag.queried"
    RAG_COLLECTION_CREATED = "rag.collection.created"
    RAG_COLLECTION_DELETED = "rag.collection.deleted"

    # Service events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    SERVICE_HEALTH_CHANGED = "service.health.changed"

    # Agent events
    AGENT_TASK_STARTED = "agent.task.started"
    AGENT_TASK_COMPLETED = "agent.task.completed"
    AGENT_TASK_FAILED = "agent.task.failed"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # Workflow events
    WORKFLOW_TRIGGERED = "workflow.triggered"
    WORKFLOW_COMPLETED = "workflow.completed"
