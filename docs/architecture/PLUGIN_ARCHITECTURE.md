# AlsaniaMCP Plugin-Based Architecture Design

## Overview

This document outlines the comprehensive plugin-based architecture for AlsaniaMCP, designed to provide modularity, maintainability, and extensibility while preserving all existing functionality.

## Core Design Principles

### 1. **Plugin-First Architecture**
- All major components (agents, embeddings, memory) are plugins
- Hot-swappable modules without system restart
- Standardized plugin interfaces and lifecycle management
- Automatic plugin discovery and registration

### 2. **Dependency Injection**
- Central service container for dependency management
- Interface-based programming with concrete implementations
- Configuration-driven service binding
- Runtime service resolution and injection

### 3. **Clear Separation of Concerns**
- Core framework provides infrastructure
- Plugins provide business logic
- Configuration drives behavior
- Events enable loose coupling

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   FastAPI   │  │  Echo Core  │  │   Agents    │        │
│  │   Routes    │  │   Service   │  │  Plugins    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│                    Plugin Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Agent     │  │ Embeddings  │  │   Memory    │        │
│  │  Plugins    │  │   Plugins   │  │  Plugins    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│                    Core Framework                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Plugin    │  │ Dependency  │  │    Event    │        │
│  │  Manager    │  │  Injection  │  │   System    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
├─────────────────────────────────────────────────────────────┤
│                 Infrastructure Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Database   │  │   Redis     │  │   Config    │        │
│  │   Access    │  │   Cache     │  │  Manager    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Plugin System Design

### Base Plugin Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

class PluginStatus(Enum):
    INACTIVE = "inactive"
    LOADING = "loading"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"

class IPlugin(ABC):
    """Base interface for all plugins"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin unique identifier"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version"""
        pass
    
    @property
    @abstractmethod
    def dependencies(self) -> List[str]:
        """List of required plugin dependencies"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the plugin"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the plugin gracefully"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if plugin is healthy"""
        pass
    
    @property
    def status(self) -> PluginStatus:
        """Current plugin status"""
        return self._status
```

### Agent Plugin Interface

```python
class IAgentPlugin(IPlugin):
    """Interface for agent plugins"""
    
    @abstractmethod
    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        """Process a message and return response"""
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Return list of agent capabilities"""
        pass
    
    @property
    @abstractmethod
    def memory_namespace(self) -> str:
        """Agent's isolated memory namespace"""
        pass
```

### Embedding Plugin Interface

```python
class IEmbeddingPlugin(IPlugin):
    """Interface for embedding plugins"""
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        pass
    
    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """Dimension of generated embeddings"""
        pass
    
    @property
    @abstractmethod
    def max_input_length(self) -> int:
        """Maximum input text length"""
        pass
```

### Memory Plugin Interface

```python
class IMemoryPlugin(IPlugin):
    """Interface for memory storage plugins"""
    
    @abstractmethod
    async def store(self, key: str, data: Any, namespace: str = "default") -> str:
        """Store data and return storage ID"""
        pass
    
    @abstractmethod
    async def retrieve(self, storage_id: str, namespace: str = "default") -> Any:
        """Retrieve data by storage ID"""
        pass
    
    @abstractmethod
    async def search(self, query: str, namespace: str = "default", 
                    limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar content"""
        pass
    
    @abstractmethod
    async def delete(self, storage_id: str, namespace: str = "default") -> bool:
        """Delete stored data"""
        pass
```

## Plugin Discovery and Registration

### Plugin Manifest

Each plugin includes a `plugin.yaml` manifest:

```yaml
name: "cypher-agent"
version: "1.0.0"
type: "agent"
description: "Code analysis and security scanning agent"
author: "Alsania Team"
license: "MIT"

dependencies:
  - "memory-postgres"
  - "embeddings-local"

configuration:
  schema:
    scan_depth:
      type: "integer"
      default: 3
      description: "Maximum directory depth for scanning"
    
entry_point: "cypher.agent:CypherAgent"
hot_reload: true
priority: 100
```

### Plugin Manager

```python
class PluginManager:
    """Central plugin management system"""
    
    def __init__(self, service_container: ServiceContainer):
        self.container = service_container
        self.plugins: Dict[str, IPlugin] = {}
        self.plugin_configs: Dict[str, Dict] = {}
        self.dependency_graph = DependencyGraph()
    
    async def discover_plugins(self, plugin_dirs: List[str]) -> None:
        """Discover plugins in specified directories"""
        pass
    
    async def load_plugin(self, plugin_name: str) -> None:
        """Load and initialize a specific plugin"""
        pass
    
    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin gracefully"""
        pass
    
    async def reload_plugin(self, plugin_name: str) -> None:
        """Hot-reload a plugin"""
        pass
    
    def get_plugins_by_type(self, plugin_type: str) -> List[IPlugin]:
        """Get all plugins of a specific type"""
        pass
```

## Service Container and Dependency Injection

```python
class ServiceContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
    
    def register_singleton(self, interface: type, implementation: type) -> None:
        """Register a singleton service"""
        pass
    
    def register_transient(self, interface: type, implementation: type) -> None:
        """Register a transient service"""
        pass
    
    def register_factory(self, interface: type, factory: Callable) -> None:
        """Register a factory function"""
        pass
    
    def resolve(self, interface: type) -> Any:
        """Resolve a service instance"""
        pass
```

## Event System

```python
class EventBus:
    """Event-driven communication system"""
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type"""
        pass
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe from an event type"""
        pass
    
    async def publish(self, event_type: str, data: Any) -> None:
        """Publish an event"""
        pass
```

## Configuration Management

```python
class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._watchers: List[Callable] = []
    
    def load_config(self, config_path: str) -> None:
        """Load configuration from file"""
        pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        pass
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        pass
    
    def watch(self, callback: Callable) -> None:
        """Watch for configuration changes"""
        pass
```

## Implementation Strategy

### Phase 1: Core Framework
1. Implement base plugin interfaces
2. Create plugin manager and service container
3. Set up event system and configuration management
4. Add plugin discovery mechanism

### Phase 2: Migrate Existing Components
1. Convert agents to plugin architecture
2. Refactor embedding system as plugins
3. Migrate memory system to plugin model
4. Update import management

### Phase 3: Testing and Validation
1. Implement comprehensive test suite
2. Add integration tests for plugin system
3. Validate hot-reload functionality
4. Performance testing and optimization

### Phase 4: Documentation and Examples
1. Create plugin development guide
2. Provide example plugins
3. Update API documentation
4. Migration guide for existing code

This architecture provides a solid foundation for modularity while maintaining backward compatibility and enabling future extensibility.
