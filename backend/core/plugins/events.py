"""
Event System for Plugin Communication

Provides an event-driven communication system that enables
loose coupling between plugins and core components.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import weakref

logger = logging.getLogger("alsaniamcp.plugins.events")


class EventPriority(Enum):
    """Event handler priority levels"""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


@dataclass
class Event:
    """Base event class"""
    type: str
    data: Any = None
    source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = f"{self.type}_{id(self)}"


@dataclass
class PluginEvent(Event):
    """Plugin-specific events"""
    plugin_name: str = ""
    plugin_version: str = ""


class PluginEventTypes:
    """Standard plugin event types"""
    PLUGIN_LOADING = "plugin.loading"
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_STARTING = "plugin.starting"
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_STOPPING = "plugin.stopping"
    PLUGIN_STOPPED = "plugin.stopped"
    PLUGIN_ERROR = "plugin.error"
    PLUGIN_HEALTH_CHECK = "plugin.health_check"
    PLUGIN_CONFIG_CHANGED = "plugin.config_changed"


class SystemEventTypes:
    """System-level event types"""
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "system.config_changed"
    HEALTH_CHECK = "system.health_check"


@dataclass
class EventHandler:
    """Event handler descriptor"""
    handler: Callable
    priority: EventPriority = EventPriority.NORMAL
    async_handler: bool = False
    once: bool = False  # Handler should be removed after first execution
    filter_func: Optional[Callable[[Event], bool]] = None
    
    def __post_init__(self):
        self.async_handler = asyncio.iscoroutinefunction(self.handler)


class EventBus:
    """Event-driven communication system"""
    
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._lock = asyncio.Lock()
        self._stats = {
            'events_published': 0,
            'handlers_executed': 0,
            'errors': 0
        }
    
    def subscribe(self, event_type: str, handler: Callable,
                 priority: EventPriority = EventPriority.NORMAL,
                 once: bool = False,
                 filter_func: Optional[Callable[[Event], bool]] = None) -> None:
        """Subscribe to an event type"""
        event_handler = EventHandler(
            handler=handler,
            priority=priority,
            once=once,
            filter_func=filter_func
        )
        
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(event_handler)
        
        # Sort handlers by priority (highest first)
        self._handlers[event_type].sort(key=lambda h: h.priority.value, reverse=True)
        
        logger.debug(f"Subscribed handler to event type: {event_type}")
    
    def subscribe_global(self, handler: Callable,
                        priority: EventPriority = EventPriority.NORMAL,
                        filter_func: Optional[Callable[[Event], bool]] = None) -> None:
        """Subscribe to all events (global handler)"""
        event_handler = EventHandler(
            handler=handler,
            priority=priority,
            filter_func=filter_func
        )
        
        self._global_handlers.append(event_handler)
        self._global_handlers.sort(key=lambda h: h.priority.value, reverse=True)
        
        logger.debug("Subscribed global event handler")
    
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Unsubscribe from an event type"""
        if event_type not in self._handlers:
            return False
        
        original_count = len(self._handlers[event_type])
        self._handlers[event_type] = [
            h for h in self._handlers[event_type] 
            if h.handler != handler
        ]
        
        removed = original_count - len(self._handlers[event_type])
        if removed > 0:
            logger.debug(f"Unsubscribed {removed} handler(s) from event type: {event_type}")
        
        return removed > 0
    
    def unsubscribe_global(self, handler: Callable) -> bool:
        """Unsubscribe from global events"""
        original_count = len(self._global_handlers)
        self._global_handlers = [
            h for h in self._global_handlers 
            if h.handler != handler
        ]
        
        removed = original_count - len(self._global_handlers)
        if removed > 0:
            logger.debug(f"Unsubscribed {removed} global handler(s)")
        
        return removed > 0
    
    async def publish(self, event: Union[Event, str], data: Any = None,
                     source: str = "unknown", **kwargs) -> None:
        """Publish an event"""
        # Convert string event type to Event object
        if isinstance(event, str):
            event = Event(type=event, data=data, source=source, **kwargs)
        
        async with self._lock:
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)
            
            self._stats['events_published'] += 1
        
        logger.debug(f"Publishing event: {event.type} from {event.source}")
        
        # Execute handlers
        await self._execute_handlers(event)
    
    async def _execute_handlers(self, event: Event) -> None:
        """Execute all handlers for an event"""
        handlers_to_execute = []
        
        # Get specific event type handlers
        if event.type in self._handlers:
            handlers_to_execute.extend(self._handlers[event.type])
        
        # Add global handlers
        handlers_to_execute.extend(self._global_handlers)
        
        # Sort by priority
        handlers_to_execute.sort(key=lambda h: h.priority.value, reverse=True)
        
        # Execute handlers
        handlers_to_remove = []
        
        for handler in handlers_to_execute:
            try:
                # Apply filter if present
                if handler.filter_func and not handler.filter_func(event):
                    continue
                
                # Execute handler
                if handler.async_handler:
                    await handler.handler(event)
                else:
                    handler.handler(event)
                
                self._stats['handlers_executed'] += 1
                
                # Mark for removal if it's a one-time handler
                if handler.once:
                    handlers_to_remove.append((event.type, handler))
                
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"Error executing event handler for {event.type}: {e}")
        
        # Remove one-time handlers
        for event_type, handler in handlers_to_remove:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]
            else:
                self._global_handlers = [
                    h for h in self._global_handlers if h != handler
                ]
    
    def get_event_history(self, event_type: Optional[str] = None,
                         limit: int = 100) -> List[Event]:
        """Get event history"""
        if event_type:
            events = [e for e in self._event_history if e.type == event_type]
        else:
            events = self._event_history.copy()
        
        return events[-limit:] if limit > 0 else events
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            **self._stats,
            'active_handlers': sum(len(handlers) for handlers in self._handlers.values()),
            'global_handlers': len(self._global_handlers),
            'event_types': len(self._handlers),
            'history_size': len(self._event_history)
        }
    
    def clear_history(self) -> None:
        """Clear event history"""
        self._event_history.clear()
        logger.debug("Event history cleared")
    
    def clear_handlers(self) -> None:
        """Clear all event handlers"""
        self._handlers.clear()
        self._global_handlers.clear()
        logger.debug("All event handlers cleared")


# Global event bus instance
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def set_event_bus(event_bus: EventBus) -> None:
    """Set the global event bus instance"""
    global _global_event_bus
    _global_event_bus = event_bus


# Convenience functions
async def publish_event(event_type: str, data: Any = None, source: str = "unknown", **kwargs) -> None:
    """Publish an event using the global event bus"""
    await get_event_bus().publish(event_type, data, source, **kwargs)


def subscribe_event(event_type: str, handler: Callable, **kwargs) -> None:
    """Subscribe to an event using the global event bus"""
    get_event_bus().subscribe(event_type, handler, **kwargs)
