"""
Plugin Manager

Central management system for all plugins, handling lifecycle,
dependencies, and coordination between different plugin types.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Any
from .interfaces import IPlugin, IAgentPlugin, IEmbeddingPlugin, IMemoryPlugin, PluginStatus, PluginType
from .container import ServiceContainer
from .events import EventBus, PluginEventTypes, PluginEvent
from .config import ConfigManager
from .discovery import PluginDiscovery, PluginManifest
from .exceptions import (
    PluginError, PluginLoadError, PluginDependencyError,
    PluginNotFoundError, PluginAlreadyLoadedError
)

logger = logging.getLogger("alsaniamcp.plugins.manager")


class PluginManager:
    """Central plugin management system"""
    
    def __init__(self, service_container: ServiceContainer, 
                 event_bus: EventBus, config_manager: ConfigManager):
        self.container = service_container
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.discovery = PluginDiscovery()
        
        # Plugin storage
        self._plugins: Dict[str, IPlugin] = {}
        self._plugin_classes: Dict[str, Type[IPlugin]] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._load_order: List[str] = []
        
        # Plugin type registries
        self._agents: Dict[str, IAgentPlugin] = {}
        self._embeddings: Dict[str, IEmbeddingPlugin] = {}
        self._memory_providers: Dict[str, IMemoryPlugin] = {}
        
        # State management
        self._startup_complete = False
        self._shutdown_initiated = False
        
        # Health monitoring
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30  # seconds
    
    async def initialize(self) -> None:
        """Initialize the plugin manager"""
        logger.info("Initializing plugin manager")
        
        # Load plugin configuration
        plugin_config = self.config_manager.get('plugins', {})
        
        # Discover plugins
        discovery_paths = plugin_config.get('discovery_paths', ['./plugins'])
        await self.discovery.discover_plugins(discovery_paths)
        
        # Auto-load plugins if enabled
        if plugin_config.get('auto_load', True):
            discovered = self.discovery.get_discovered_plugins()
            await self.load_plugins(list(discovered.keys()))
        
        # Start health monitoring
        if plugin_config.get('health_monitoring', True):
            await self._start_health_monitoring()
        
        self._startup_complete = True
        logger.info("Plugin manager initialization complete")
    
    async def discover_plugins(self, discovery_paths: Optional[List[str]] = None) -> Dict[str, PluginManifest]:
        """Discover plugins in specified paths"""
        if discovery_paths is None:
            discovery_paths = self.config_manager.get('plugins.discovery_paths', ['./plugins'])
        
        return await self.discovery.discover_plugins(discovery_paths)
    
    async def load_plugins(self, plugin_names: List[str]) -> None:
        """Load multiple plugins with dependency resolution"""
        try:
            # Resolve dependencies and get load order
            load_order = self.discovery.resolve_dependencies(plugin_names)
            
            logger.info(f"Loading plugins in order: {load_order}")
            
            # Load plugins in dependency order
            for plugin_name in load_order:
                if plugin_name not in self._plugins:
                    await self.load_plugin(plugin_name)
            
            logger.info(f"Successfully loaded {len(load_order)} plugins")
            
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")
            raise
    
    async def load_plugin(self, plugin_name: str) -> IPlugin:
        """Load a single plugin"""
        if plugin_name in self._plugins:
            raise PluginAlreadyLoadedError(f"Plugin already loaded: {plugin_name}")
        
        try:
            # Publish loading event
            await self.event_bus.publish(PluginEvent(
                type=PluginEventTypes.PLUGIN_LOADING,
                plugin_name=plugin_name,
                source="plugin_manager"
            ))
            
            # Load plugin class
            plugin_class = await self.discovery.load_plugin(plugin_name)
            self._plugin_classes[plugin_name] = plugin_class
            
            # Create plugin instance
            plugin_instance = plugin_class()
            
            # Get plugin configuration
            plugin_config = self._get_plugin_config(plugin_name)
            
            # Initialize plugin
            await plugin_instance.initialize(plugin_config)
            
            # Store plugin
            self._plugins[plugin_name] = plugin_instance
            self._plugin_configs[plugin_name] = plugin_config
            self._load_order.append(plugin_name)
            
            # Register plugin in appropriate type registry
            await self._register_plugin_by_type(plugin_instance)
            
            # Register plugin services in container
            await self._register_plugin_services(plugin_instance)
            
            # Start plugin
            await plugin_instance.start()
            
            # Publish loaded event
            await self.event_bus.publish(PluginEvent(
                type=PluginEventTypes.PLUGIN_LOADED,
                plugin_name=plugin_name,
                plugin_version=plugin_instance.metadata.version,
                source="plugin_manager"
            ))
            
            logger.info(f"Successfully loaded plugin: {plugin_name}")
            return plugin_instance
            
        except Exception as e:
            # Publish error event
            await self.event_bus.publish(PluginEvent(
                type=PluginEventTypes.PLUGIN_ERROR,
                plugin_name=plugin_name,
                data={'error': str(e)},
                source="plugin_manager"
            ))
            
            # Clean up partial state
            await self._cleanup_failed_plugin(plugin_name)
            
            raise PluginLoadError(f"Failed to load plugin {plugin_name}", plugin_name, e)
    
    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin"""
        if plugin_name not in self._plugins:
            raise PluginNotFoundError(f"Plugin not loaded: {plugin_name}")
        
        try:
            plugin = self._plugins[plugin_name]
            
            # Publish stopping event
            await self.event_bus.publish(PluginEvent(
                type=PluginEventTypes.PLUGIN_STOPPING,
                plugin_name=plugin_name,
                source="plugin_manager"
            ))
            
            # Stop plugin
            await plugin.stop()
            
            # Unregister from type registries
            await self._unregister_plugin_by_type(plugin)
            
            # Remove from storage
            del self._plugins[plugin_name]
            if plugin_name in self._plugin_configs:
                del self._plugin_configs[plugin_name]
            if plugin_name in self._load_order:
                self._load_order.remove(plugin_name)
            
            # Publish stopped event
            await self.event_bus.publish(PluginEvent(
                type=PluginEventTypes.PLUGIN_STOPPED,
                plugin_name=plugin_name,
                source="plugin_manager"
            ))
            
            logger.info(f"Successfully unloaded plugin: {plugin_name}")
            
        except Exception as e:
            await self.event_bus.publish(PluginEvent(
                type=PluginEventTypes.PLUGIN_ERROR,
                plugin_name=plugin_name,
                data={'error': str(e)},
                source="plugin_manager"
            ))
            raise
    
    async def reload_plugin(self, plugin_name: str) -> IPlugin:
        """Hot-reload a plugin"""
        if plugin_name not in self._plugins:
            raise PluginNotFoundError(f"Plugin not loaded: {plugin_name}")
        
        plugin = self._plugins[plugin_name]
        if not plugin.metadata.hot_reload_supported:
            raise PluginError(f"Plugin {plugin_name} does not support hot-reload")
        
        try:
            logger.info(f"Hot-reloading plugin: {plugin_name}")
            
            # Unload current instance
            await self.unload_plugin(plugin_name)
            
            # Reload plugin class
            await self.discovery.reload_plugin(plugin_name)
            
            # Load new instance
            return await self.load_plugin(plugin_name)
            
        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            raise
    
    def get_plugin(self, plugin_name: str) -> Optional[IPlugin]:
        """Get a loaded plugin by name"""
        return self._plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[IPlugin]:
        """Get all plugins of a specific type"""
        return [
            plugin for plugin in self._plugins.values()
            if plugin.metadata.type == plugin_type
        ]
    
    def get_agents(self) -> Dict[str, IAgentPlugin]:
        """Get all loaded agent plugins"""
        return self._agents.copy()
    
    def get_embeddings(self) -> Dict[str, IEmbeddingPlugin]:
        """Get all loaded embedding plugins"""
        return self._embeddings.copy()
    
    def get_memory_providers(self) -> Dict[str, IMemoryPlugin]:
        """Get all loaded memory provider plugins"""
        return self._memory_providers.copy()
    
    def get_loaded_plugins(self) -> Dict[str, IPlugin]:
        """Get all loaded plugins"""
        return self._plugins.copy()
    
    async def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """Get the status of a specific plugin"""
        plugin = self._plugins.get(plugin_name)
        return plugin.status if plugin else None
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all plugins"""
        results = {}
        
        for plugin_name, plugin in self._plugins.items():
            try:
                results[plugin_name] = await plugin.health_check()
            except Exception as e:
                logger.warning(f"Health check failed for plugin {plugin_name}: {e}")
                results[plugin_name] = False
        
        return results
    
    async def shutdown(self) -> None:
        """Shutdown all plugins"""
        if self._shutdown_initiated:
            return
        
        self._shutdown_initiated = True
        logger.info("Shutting down plugin manager")
        
        # Stop health monitoring
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Unload plugins in reverse order
        for plugin_name in reversed(self._load_order.copy()):
            try:
                await self.unload_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Error unloading plugin {plugin_name}: {e}")
        
        logger.info("Plugin manager shutdown complete")
    
    def _get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """Get configuration for a plugin"""
        # Get plugin-specific config
        plugin_config = self.config_manager.get(f'plugins.{plugin_name}', {})
        
        # Get default config from manifest
        manifest = self.discovery.get_plugin_manifest(plugin_name)
        if manifest and manifest.configuration_schema:
            # Apply defaults from schema
            for key, spec in manifest.configuration_schema.items():
                if key not in plugin_config and 'default' in spec:
                    plugin_config[key] = spec['default']
        
        return plugin_config
    
    async def _register_plugin_by_type(self, plugin: IPlugin) -> None:
        """Register plugin in appropriate type registry"""
        if isinstance(plugin, IAgentPlugin):
            self._agents[plugin.metadata.name] = plugin
        elif isinstance(plugin, IEmbeddingPlugin):
            self._embeddings[plugin.metadata.name] = plugin
        elif isinstance(plugin, IMemoryPlugin):
            self._memory_providers[plugin.metadata.name] = plugin
    
    async def _unregister_plugin_by_type(self, plugin: IPlugin) -> None:
        """Unregister plugin from type registries"""
        plugin_name = plugin.metadata.name
        
        if plugin_name in self._agents:
            del self._agents[plugin_name]
        if plugin_name in self._embeddings:
            del self._embeddings[plugin_name]
        if plugin_name in self._memory_providers:
            del self._memory_providers[plugin_name]
    
    async def _register_plugin_services(self, plugin: IPlugin) -> None:
        """Register plugin services in the service container"""
        # Register the plugin instance itself
        self.container.register_instance(type(plugin), plugin)
        
        # Register by interface types
        if isinstance(plugin, IAgentPlugin):
            self.container.register_instance(IAgentPlugin, plugin)
        elif isinstance(plugin, IEmbeddingPlugin):
            self.container.register_instance(IEmbeddingPlugin, plugin)
        elif isinstance(plugin, IMemoryPlugin):
            self.container.register_instance(IMemoryPlugin, plugin)
    
    async def _cleanup_failed_plugin(self, plugin_name: str) -> None:
        """Clean up state for a failed plugin load"""
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
        if plugin_name in self._plugin_configs:
            del self._plugin_configs[plugin_name]
        if plugin_name in self._plugin_classes:
            del self._plugin_classes[plugin_name]
        if plugin_name in self._load_order:
            self._load_order.remove(plugin_name)
    
    async def _start_health_monitoring(self) -> None:
        """Start health monitoring for all plugins"""
        self._health_check_interval = self.config_manager.get('plugins.health_check_interval', 30)
        self._health_check_task = asyncio.create_task(self._health_monitor_loop())
    
    async def _health_monitor_loop(self) -> None:
        """Health monitoring loop"""
        while not self._shutdown_initiated:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                if self._plugins:
                    health_results = await self.health_check_all()
                    
                    # Log unhealthy plugins
                    unhealthy = [name for name, healthy in health_results.items() if not healthy]
                    if unhealthy:
                        logger.warning(f"Unhealthy plugins detected: {unhealthy}")
                    
                    # Publish health check event
                    await self.event_bus.publish(PluginEvent(
                        type=PluginEventTypes.PLUGIN_HEALTH_CHECK,
                        data={'results': health_results},
                        source="plugin_manager"
                    ))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
