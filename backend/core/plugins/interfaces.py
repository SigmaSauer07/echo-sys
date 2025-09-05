"""
Core plugin interfaces for AlsaniaMCP

Defines the base interfaces that all plugins must implement,
providing standardized contracts for different plugin types.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import asyncio
import logging

logger = logging.getLogger("alsaniamcp.plugins.interfaces")


class PluginStatus(Enum):
    """Plugin lifecycle status"""
    INACTIVE = "inactive"
    LOADING = "loading"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


class PluginType(Enum):
    """Plugin type categories"""
    AGENT = "agent"
    EMBEDDING = "embedding"
    MEMORY = "memory"
    MIDDLEWARE = "middleware"
    EXTENSION = "extension"


class PluginMetadata:
    """Plugin metadata container"""
    
    def __init__(self, name: str, version: str, plugin_type: PluginType,
                 description: str = "", author: str = "", license: str = ""):
        self.name = name
        self.version = version
        self.type = plugin_type
        self.description = description
        self.author = author
        self.license = license
        self.dependencies: List[str] = []
        self.configuration_schema: Dict[str, Any] = {}
        self.hot_reload_supported = True
        self.priority = 100


class IPlugin(ABC):
    """Base interface for all plugins"""
    
    def __init__(self):
        self._status = PluginStatus.INACTIVE
        self._config: Dict[str, Any] = {}
        self._logger = logging.getLogger(f"alsaniamcp.plugins.{self.metadata.name}")
        self._health_check_interval = 30  # seconds
        self._last_health_check: Optional[float] = None
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata"""
        pass
    
    @property
    def status(self) -> PluginStatus:
        """Current plugin status"""
        return self._status
    
    @property
    def config(self) -> Dict[str, Any]:
        """Plugin configuration"""
        return self._config.copy()
    
    @property
    def logger(self) -> logging.Logger:
        """Plugin logger"""
        return self._logger
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration"""
        try:
            self._status = PluginStatus.LOADING
            self._config = config.copy()
            
            # Validate configuration against schema
            await self._validate_config(config)
            
            # Plugin-specific initialization
            await self._initialize_impl(config)
            
            self._logger.info(f"Plugin {self.metadata.name} initialized successfully")
            
        except Exception as e:
            self._status = PluginStatus.ERROR
            self._logger.error(f"Failed to initialize plugin {self.metadata.name}: {e}")
            raise
    
    async def start(self) -> None:
        """Start the plugin"""
        try:
            if self._status != PluginStatus.LOADING:
                raise RuntimeError(f"Plugin {self.metadata.name} must be initialized before starting")
            
            await self._start_impl()
            self._status = PluginStatus.ACTIVE
            
            # Start health check monitoring if supported
            if hasattr(self, '_start_health_monitoring'):
                asyncio.create_task(self._start_health_monitoring())
            
            self._logger.info(f"Plugin {self.metadata.name} started successfully")
            
        except Exception as e:
            self._status = PluginStatus.ERROR
            self._logger.error(f"Failed to start plugin {self.metadata.name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the plugin gracefully"""
        try:
            self._status = PluginStatus.STOPPING
            await self._stop_impl()
            self._status = PluginStatus.STOPPED
            
            self._logger.info(f"Plugin {self.metadata.name} stopped successfully")
            
        except Exception as e:
            self._status = PluginStatus.ERROR
            self._logger.error(f"Failed to stop plugin {self.metadata.name}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if plugin is healthy"""
        try:
            if self._status != PluginStatus.ACTIVE:
                return False
            
            result = await self._health_check_impl()
            self._last_health_check = asyncio.get_event_loop().time()
            return result
            
        except Exception as e:
            self._logger.warning(f"Health check failed for plugin {self.metadata.name}: {e}")
            return False
    
    async def reload(self) -> None:
        """Reload the plugin (hot-reload)"""
        if not self.metadata.hot_reload_supported:
            raise RuntimeError(f"Plugin {self.metadata.name} does not support hot-reload")
        
        try:
            self._logger.info(f"Reloading plugin {self.metadata.name}")
            
            # Stop current instance
            await self.stop()
            
            # Reload implementation
            await self._reload_impl()
            
            # Restart with current config
            await self.initialize(self._config)
            await self.start()
            
            self._logger.info(f"Plugin {self.metadata.name} reloaded successfully")
            
        except Exception as e:
            self._status = PluginStatus.ERROR
            self._logger.error(f"Failed to reload plugin {self.metadata.name}: {e}")
            raise
    
    # Abstract methods that plugins must implement
    @abstractmethod
    async def _initialize_impl(self, config: Dict[str, Any]) -> None:
        """Plugin-specific initialization logic"""
        pass
    
    @abstractmethod
    async def _start_impl(self) -> None:
        """Plugin-specific start logic"""
        pass
    
    @abstractmethod
    async def _stop_impl(self) -> None:
        """Plugin-specific stop logic"""
        pass
    
    @abstractmethod
    async def _health_check_impl(self) -> bool:
        """Plugin-specific health check logic"""
        pass
    
    async def _reload_impl(self) -> None:
        """Plugin-specific reload logic (optional)"""
        pass
    
    async def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration against schema (optional)"""
        # Basic validation - can be overridden for complex schemas
        schema = self.metadata.configuration_schema
        if not schema:
            return
        
        for key, spec in schema.items():
            if spec.get('required', False) and key not in config:
                raise ValueError(f"Required configuration key '{key}' missing")


class IAgentPlugin(IPlugin):
    """Interface for agent plugins"""
    
    @property
    @abstractmethod
    def memory_namespace(self) -> str:
        """Agent's isolated memory namespace"""
        pass
    
    @abstractmethod
    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        """Process a message and return response"""
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """Return list of agent capabilities"""
        pass
    
    async def get_agent_info(self) -> Dict[str, Any]:
        """Get comprehensive agent information"""
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'status': self.status.value,
            'capabilities': await self.get_capabilities(),
            'memory_namespace': self.memory_namespace,
            'description': self.metadata.description
        }


class IEmbeddingPlugin(IPlugin):
    """Interface for embedding plugins"""
    
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
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        pass
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (default implementation)"""
        results = []
        for text in texts:
            embedding = await self.embed_text(text)
            results.append(embedding)
        return results
    
    async def get_embedding_info(self) -> Dict[str, Any]:
        """Get embedding model information"""
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'dimension': self.embedding_dimension,
            'max_input_length': self.max_input_length,
            'status': self.status.value
        }


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
    
    async def list_namespaces(self) -> List[str]:
        """List available namespaces (optional)"""
        return ["default"]
    
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get storage system information"""
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'status': self.status.value,
            'namespaces': await self.list_namespaces()
        }
