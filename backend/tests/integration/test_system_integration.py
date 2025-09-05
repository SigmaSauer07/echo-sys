"""
Integration tests for the AlsaniaMCP system

Tests the integration between different components including
plugins, services, and external dependencies.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from backend.core.plugins import (
    PluginManager, ServiceContainer, EventBus, ConfigManager,
    IAgentPlugin, IEmbeddingPlugin, IMemoryPlugin,
    PluginStatus, PluginType, PluginMetadata
)


class MockAgentPlugin(IAgentPlugin):
    """Mock agent plugin for integration testing"""
    
    def __init__(self, name="test-agent"):
        super().__init__()
        self._name = name
        self._metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            plugin_type=PluginType.AGENT
        )
        self._capabilities = ["test", "mock"]
        self._memory_namespace = f"{name}_memory"
    
    @property
    def metadata(self):
        return self._metadata
    
    @property
    def memory_namespace(self):
        return self._memory_namespace
    
    async def _initialize_impl(self, config):
        self.config = config
        self.initialized = True
    
    async def _start_impl(self):
        self.started = True
    
    async def _stop_impl(self):
        self.stopped = True
    
    async def _health_check_impl(self):
        return True
    
    async def process_message(self, message: str, context: dict) -> str:
        return f"Mock response to: {message}"
    
    async def get_capabilities(self) -> list:
        return self._capabilities


class MockEmbeddingPlugin(IEmbeddingPlugin):
    """Mock embedding plugin for integration testing"""
    
    def __init__(self, name="test-embeddings"):
        super().__init__()
        self._name = name
        self._metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            plugin_type=PluginType.EMBEDDING
        )
        self._dimension = 384
        self._max_length = 512
    
    @property
    def metadata(self):
        return self._metadata
    
    @property
    def embedding_dimension(self):
        return self._dimension
    
    @property
    def max_input_length(self):
        return self._max_length
    
    async def _initialize_impl(self, config):
        self.config = config
        self.initialized = True
    
    async def _start_impl(self):
        self.started = True
    
    async def _stop_impl(self):
        self.stopped = True
    
    async def _health_check_impl(self):
        return True
    
    async def embed_text(self, text: str) -> list:
        # Return mock embedding (zeros with length = dimension)
        return [0.0] * self._dimension


class MockMemoryPlugin(IMemoryPlugin):
    """Mock memory plugin for integration testing"""
    
    def __init__(self, name="test-memory"):
        super().__init__()
        self._name = name
        self._metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            plugin_type=PluginType.MEMORY
        )
        self._storage = {}
        self._namespaces = set(["default"])
    
    @property
    def metadata(self):
        return self._metadata
    
    async def _initialize_impl(self, config):
        self.config = config
        self.initialized = True
    
    async def _start_impl(self):
        self.started = True
    
    async def _stop_impl(self):
        self.stopped = True
    
    async def _health_check_impl(self):
        return True
    
    async def store(self, key: str, data, namespace: str = "default") -> str:
        storage_id = f"{namespace}:{key}"
        self._storage[storage_id] = data
        self._namespaces.add(namespace)
        return storage_id
    
    async def retrieve(self, storage_id: str, namespace: str = "default"):
        return self._storage.get(storage_id)
    
    async def search(self, query: str, namespace: str = "default", limit: int = 10) -> list:
        # Simple mock search
        results = []
        for storage_id, data in self._storage.items():
            if storage_id.startswith(f"{namespace}:") and query.lower() in str(data).lower():
                results.append({
                    'id': storage_id,
                    'data': data,
                    'score': 0.8
                })
                if len(results) >= limit:
                    break
        return results
    
    async def delete(self, storage_id: str, namespace: str = "default") -> bool:
        if storage_id in self._storage:
            del self._storage[storage_id]
            return True
        return False
    
    async def list_namespaces(self) -> list:
        return list(self._namespaces)


@pytest.mark.integration
class TestSystemIntegration:
    """Test system-wide integration"""
    
    @pytest.fixture
    async def integrated_system(self, temp_dir):
        """Set up a complete integrated system for testing"""
        # Create configuration
        config_data = {
            'plugins': {
                'discovery_paths': [str(temp_dir / 'plugins')],
                'auto_load': False,
                'hot_reload': True,
                'health_check_interval': 5
            },
            'logging': {
                'level': 'DEBUG'
            },
            'system': {
                'health_check_interval': 5
            }
        }
        
        config_file = temp_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Set up components
        service_container = ServiceContainer()
        event_bus = EventBus()
        config_manager = ConfigManager(event_bus)
        
        config_manager.add_source("test", str(config_file), "json")
        await config_manager.load_all()
        
        plugin_manager = PluginManager(service_container, event_bus, config_manager)
        
        # Register mock plugins directly (simulating discovery)
        agent_plugin = MockAgentPlugin()
        embedding_plugin = MockEmbeddingPlugin()
        memory_plugin = MockMemoryPlugin()
        
        # Initialize plugins
        await agent_plugin.initialize({})
        await agent_plugin.start()
        
        await embedding_plugin.initialize({})
        await embedding_plugin.start()
        
        await memory_plugin.initialize({})
        await memory_plugin.start()
        
        # Register in plugin manager
        plugin_manager._plugins[agent_plugin.metadata.name] = agent_plugin
        plugin_manager._agents[agent_plugin.metadata.name] = agent_plugin
        
        plugin_manager._plugins[embedding_plugin.metadata.name] = embedding_plugin
        plugin_manager._embeddings[embedding_plugin.metadata.name] = embedding_plugin
        
        plugin_manager._plugins[memory_plugin.metadata.name] = memory_plugin
        plugin_manager._memory_providers[memory_plugin.metadata.name] = memory_plugin
        
        # Register services in container
        service_container.register_instance(IAgentPlugin, agent_plugin)
        service_container.register_instance(IEmbeddingPlugin, embedding_plugin)
        service_container.register_instance(IMemoryPlugin, memory_plugin)
        
        yield {
            'plugin_manager': plugin_manager,
            'service_container': service_container,
            'event_bus': event_bus,
            'config_manager': config_manager,
            'agent_plugin': agent_plugin,
            'embedding_plugin': embedding_plugin,
            'memory_plugin': memory_plugin
        }
        
        # Cleanup
        await plugin_manager.shutdown()
        await config_manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_plugin_communication(self, integrated_system):
        """Test communication between different plugin types"""
        system = integrated_system
        agent = system['agent_plugin']
        memory = system['memory_plugin']
        embeddings = system['embedding_plugin']
        
        # Test agent processing message
        response = await agent.process_message("test message", {})
        assert "Mock response to: test message" in response
        
        # Test storing result in memory
        storage_id = await memory.store("agent_response", response, agent.memory_namespace)
        assert storage_id.startswith(agent.memory_namespace)
        
        # Test retrieving from memory
        retrieved = await memory.retrieve(storage_id, agent.memory_namespace)
        assert retrieved == response
        
        # Test embedding generation
        embedding = await embeddings.embed_text("test text")
        assert len(embedding) == embeddings.embedding_dimension
        assert all(isinstance(x, float) for x in embedding)
    
    @pytest.mark.asyncio
    async def test_service_container_integration(self, integrated_system):
        """Test service container integration with plugins"""
        system = integrated_system
        container = system['service_container']
        
        # Resolve services
        agent_service = container.resolve(IAgentPlugin)
        embedding_service = container.resolve(IEmbeddingPlugin)
        memory_service = container.resolve(IMemoryPlugin)
        
        assert agent_service is system['agent_plugin']
        assert embedding_service is system['embedding_plugin']
        assert memory_service is system['memory_plugin']
    
    @pytest.mark.asyncio
    async def test_event_system_integration(self, integrated_system):
        """Test event system integration across components"""
        system = integrated_system
        event_bus = system['event_bus']
        
        # Track events
        received_events = []
        
        def event_handler(event):
            received_events.append(event)
        
        event_bus.subscribe("test.integration", event_handler)
        
        # Publish event
        await event_bus.publish("test.integration", data="integration_test")
        
        assert len(received_events) == 1
        assert received_events[0].type == "test.integration"
        assert received_events[0].data == "integration_test"
    
    @pytest.mark.asyncio
    async def test_configuration_integration(self, integrated_system):
        """Test configuration integration with plugins"""
        system = integrated_system
        config_manager = system['config_manager']
        
        # Test configuration access
        plugin_config = config_manager.get('plugins')
        assert plugin_config is not None
        assert plugin_config.get('hot_reload') is True
        
        # Test configuration change notification
        changes = []
        
        def config_watcher(key, old_value, new_value):
            changes.append((key, old_value, new_value))
        
        config_manager.watch(config_watcher)
        config_manager.set('test.setting', 'test_value')
        
        assert len(changes) == 1
        assert changes[0][0] == 'test.setting'
        assert changes[0][2] == 'test_value'
    
    @pytest.mark.asyncio
    async def test_plugin_health_monitoring(self, integrated_system):
        """Test integrated health monitoring"""
        system = integrated_system
        plugin_manager = system['plugin_manager']
        
        # Test health check across all plugins
        health_results = await plugin_manager.health_check_all()
        
        assert len(health_results) == 3  # agent, embedding, memory
        assert all(health_results.values())  # All should be healthy
    
    @pytest.mark.asyncio
    async def test_memory_search_integration(self, integrated_system):
        """Test integrated memory search functionality"""
        system = integrated_system
        memory = system['memory_plugin']
        agent = system['agent_plugin']
        
        # Store multiple items
        await memory.store("item1", "This is a test document", agent.memory_namespace)
        await memory.store("item2", "Another test item", agent.memory_namespace)
        await memory.store("item3", "Different content", agent.memory_namespace)
        
        # Search for items
        results = await memory.search("test", agent.memory_namespace, limit=10)
        
        assert len(results) == 2  # Should find 2 items with "test"
        assert all('test' in str(result['data']).lower() for result in results)
    
    @pytest.mark.asyncio
    async def test_plugin_isolation(self, integrated_system):
        """Test that plugins are properly isolated"""
        system = integrated_system
        memory = system['memory_plugin']
        agent = system['agent_plugin']
        
        # Store data in agent's namespace
        agent_data = "agent specific data"
        await memory.store("test_key", agent_data, agent.memory_namespace)
        
        # Try to retrieve from default namespace (should not find it)
        default_result = await memory.retrieve(f"default:test_key", "default")
        assert default_result is None
        
        # Retrieve from correct namespace
        agent_result = await memory.retrieve(f"{agent.memory_namespace}:test_key", agent.memory_namespace)
        assert agent_result == agent_data
    
    @pytest.mark.asyncio
    async def test_system_shutdown(self, integrated_system):
        """Test graceful system shutdown"""
        system = integrated_system
        plugin_manager = system['plugin_manager']
        config_manager = system['config_manager']
        
        # Verify plugins are active
        assert system['agent_plugin'].status == PluginStatus.ACTIVE
        assert system['embedding_plugin'].status == PluginStatus.ACTIVE
        assert system['memory_plugin'].status == PluginStatus.ACTIVE
        
        # Shutdown system
        await plugin_manager.shutdown()
        await config_manager.shutdown()
        
        # Verify plugins are stopped
        assert system['agent_plugin'].status == PluginStatus.STOPPED
        assert system['embedding_plugin'].status == PluginStatus.STOPPED
        assert system['memory_plugin'].status == PluginStatus.STOPPED
