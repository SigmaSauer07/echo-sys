"""
Unit tests for the plugin system

Tests the core plugin infrastructure including interfaces,
manager, container, events, and configuration.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from backend.core.plugins import (
    IPlugin, IAgentPlugin, IEmbeddingPlugin, IMemoryPlugin,
    PluginManager, ServiceContainer, EventBus, ConfigManager,
    PluginStatus, PluginType, PluginMetadata,
    PluginError, PluginLoadError, PluginDependencyError
)


class TestPluginInterfaces:
    """Test plugin interfaces and base classes"""
    
    def test_plugin_metadata_creation(self):
        """Test plugin metadata creation"""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            plugin_type=PluginType.EXTENSION,
            description="Test plugin"
        )
        
        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.type == PluginType.EXTENSION
        assert metadata.description == "Test plugin"
        assert metadata.dependencies == []
        assert metadata.hot_reload_supported is True
    
    def test_plugin_status_enum(self):
        """Test plugin status enumeration"""
        assert PluginStatus.INACTIVE.value == "inactive"
        assert PluginStatus.LOADING.value == "loading"
        assert PluginStatus.ACTIVE.value == "active"
        assert PluginStatus.ERROR.value == "error"
        assert PluginStatus.STOPPING.value == "stopping"
        assert PluginStatus.STOPPED.value == "stopped"
    
    def test_plugin_type_enum(self):
        """Test plugin type enumeration"""
        assert PluginType.AGENT.value == "agent"
        assert PluginType.EMBEDDING.value == "embedding"
        assert PluginType.MEMORY.value == "memory"
        assert PluginType.MIDDLEWARE.value == "middleware"
        assert PluginType.EXTENSION.value == "extension"


class MockPlugin(IPlugin):
    """Mock plugin for testing"""
    
    def __init__(self, name="mock-plugin", fail_init=False, fail_start=False, fail_health=False):
        super().__init__()
        self._name = name
        self._fail_init = fail_init
        self._fail_start = fail_start
        self._fail_health = fail_health
        self._metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            plugin_type=PluginType.EXTENSION
        )
    
    @property
    def metadata(self):
        return self._metadata
    
    async def _initialize_impl(self, config):
        if self._fail_init:
            raise Exception("Mock initialization failure")
        self.initialized = True
    
    async def _start_impl(self):
        if self._fail_start:
            raise Exception("Mock start failure")
        self.started = True
    
    async def _stop_impl(self):
        self.stopped = True
    
    async def _health_check_impl(self):
        if self._fail_health:
            return False
        return True


class TestServiceContainer:
    """Test dependency injection container"""
    
    @pytest.fixture
    def container(self):
        return ServiceContainer()
    
    def test_register_singleton(self, container):
        """Test singleton service registration"""
        class TestService:
            def __init__(self):
                self.value = "test"
        
        container.register_singleton(TestService, TestService)
        
        # Should return same instance
        instance1 = container.resolve(TestService)
        instance2 = container.resolve(TestService)
        
        assert instance1 is instance2
        assert instance1.value == "test"
    
    def test_register_transient(self, container):
        """Test transient service registration"""
        class TestService:
            def __init__(self):
                self.value = "test"
        
        container.register_transient(TestService, TestService)
        
        # Should return different instances
        instance1 = container.resolve(TestService)
        instance2 = container.resolve(TestService)
        
        assert instance1 is not instance2
        assert instance1.value == instance2.value == "test"
    
    def test_register_instance(self, container):
        """Test instance registration"""
        class TestService:
            def __init__(self, value):
                self.value = value
        
        instance = TestService("test_value")
        container.register_instance(TestService, instance)
        
        resolved = container.resolve(TestService)
        assert resolved is instance
        assert resolved.value == "test_value"
    
    def test_dependency_injection(self, container):
        """Test constructor dependency injection"""
        class Dependency:
            def __init__(self):
                self.name = "dependency"
        
        class Service:
            def __init__(self, dep: Dependency):
                self.dependency = dep
        
        container.register_singleton(Dependency, Dependency)
        container.register_transient(Service, Service)
        
        service = container.resolve(Service)
        assert service.dependency.name == "dependency"
    
    def test_service_not_registered(self, container):
        """Test resolving unregistered service"""
        class UnregisteredService:
            pass
        
        with pytest.raises(Exception):  # ServiceResolutionError
            container.resolve(UnregisteredService)


class TestEventBus:
    """Test event system"""
    
    @pytest.fixture
    def event_bus(self):
        return EventBus()
    
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        """Test basic event subscription and publishing"""
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        event_bus.subscribe("test.event", handler)
        await event_bus.publish("test.event", data="test_data")
        
        assert len(received_events) == 1
        assert received_events[0].type == "test.event"
        assert received_events[0].data == "test_data"
    
    @pytest.mark.asyncio
    async def test_async_handler(self, event_bus):
        """Test async event handler"""
        received_events = []
        
        async def async_handler(event):
            received_events.append(event)
        
        event_bus.subscribe("test.async", async_handler)
        await event_bus.publish("test.async", data="async_data")
        
        assert len(received_events) == 1
        assert received_events[0].data == "async_data"
    
    @pytest.mark.asyncio
    async def test_event_priority(self, event_bus):
        """Test event handler priority"""
        execution_order = []
        
        def low_priority(event):
            execution_order.append("low")
        
        def high_priority(event):
            execution_order.append("high")
        
        from backend.core.plugins.events import EventPriority
        
        event_bus.subscribe("test.priority", low_priority, priority=EventPriority.LOW)
        event_bus.subscribe("test.priority", high_priority, priority=EventPriority.HIGH)
        
        await event_bus.publish("test.priority")
        
        assert execution_order == ["high", "low"]
    
    @pytest.mark.asyncio
    async def test_one_time_handler(self, event_bus):
        """Test one-time event handler"""
        call_count = 0
        
        def once_handler(event):
            nonlocal call_count
            call_count += 1
        
        event_bus.subscribe("test.once", once_handler, once=True)
        
        await event_bus.publish("test.once")
        await event_bus.publish("test.once")
        
        assert call_count == 1
    
    def test_unsubscribe(self, event_bus):
        """Test event handler unsubscription"""
        def handler(event):
            pass
        
        event_bus.subscribe("test.unsub", handler)
        assert event_bus.unsubscribe("test.unsub", handler) is True
        assert event_bus.unsubscribe("test.unsub", handler) is False


class TestConfigManager:
    """Test configuration management"""
    
    @pytest.mark.asyncio
    async def test_config_loading(self, temp_dir):
        """Test configuration loading from file"""
        config_manager = ConfigManager()
        
        # Create test config file
        config_file = temp_dir / "test.json"
        import json
        test_config = {"test_key": "test_value", "nested": {"key": "value"}}
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        config_manager.add_source("test", str(config_file), "json")
        await config_manager.load_all()
        
        assert config_manager.get("test_key") == "test_value"
        assert config_manager.get("nested.key") == "value"
        assert config_manager.get("nonexistent", "default") == "default"
    
    @pytest.mark.asyncio
    async def test_config_merging(self, temp_dir):
        """Test configuration merging from multiple sources"""
        config_manager = ConfigManager()
        
        # Create base config
        base_config = temp_dir / "base.json"
        import json
        with open(base_config, 'w') as f:
            json.dump({"base": "value", "shared": "base_value"}, f)
        
        # Create override config
        override_config = temp_dir / "override.json"
        with open(override_config, 'w') as f:
            json.dump({"override": "value", "shared": "override_value"}, f)
        
        config_manager.add_source("base", str(base_config), "json", priority=100)
        config_manager.add_source("override", str(override_config), "json", priority=200)
        await config_manager.load_all()
        
        assert config_manager.get("base") == "value"
        assert config_manager.get("override") == "value"
        assert config_manager.get("shared") == "override_value"  # Higher priority wins
    
    def test_config_watching(self, config_manager):
        """Test configuration change watching"""
        changes = []
        
        def watcher(key, old_value, new_value):
            changes.append((key, old_value, new_value))
        
        config_manager.watch(watcher)
        config_manager.set("test_key", "new_value")
        
        assert len(changes) == 1
        assert changes[0] == ("test_key", None, "new_value")


class TestPluginManager:
    """Test plugin manager"""
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self, plugin_manager):
        """Test complete plugin lifecycle"""
        # Mock plugin discovery
        mock_plugin = MockPlugin("test-plugin")
        
        with patch.object(plugin_manager.discovery, 'load_plugin', return_value=MockPlugin):
            with patch.object(plugin_manager.discovery, 'get_plugin_manifest') as mock_manifest:
                mock_manifest.return_value = mock_plugin.metadata
                
                # Load plugin
                loaded_plugin = await plugin_manager.load_plugin("test-plugin")
                
                assert loaded_plugin.status == PluginStatus.ACTIVE
                assert plugin_manager.get_plugin("test-plugin") is not None
                
                # Unload plugin
                await plugin_manager.unload_plugin("test-plugin")
                
                assert plugin_manager.get_plugin("test-plugin") is None
    
    @pytest.mark.asyncio
    async def test_plugin_health_check(self, plugin_manager):
        """Test plugin health checking"""
        mock_plugin = MockPlugin("healthy-plugin")
        unhealthy_plugin = MockPlugin("unhealthy-plugin", fail_health=True)
        
        # Add plugins to manager (mock the loading process)
        plugin_manager._plugins["healthy-plugin"] = mock_plugin
        plugin_manager._plugins["unhealthy-plugin"] = unhealthy_plugin
        
        # Set status to active
        mock_plugin._status = PluginStatus.ACTIVE
        unhealthy_plugin._status = PluginStatus.ACTIVE
        
        health_results = await plugin_manager.health_check_all()
        
        assert health_results["healthy-plugin"] is True
        assert health_results["unhealthy-plugin"] is False
    
    @pytest.mark.asyncio
    async def test_plugin_error_handling(self, plugin_manager):
        """Test plugin error handling"""
        failing_plugin = MockPlugin("failing-plugin", fail_init=True)
        
        with patch.object(plugin_manager.discovery, 'load_plugin', return_value=MockPlugin):
            with patch.object(plugin_manager.discovery, 'get_plugin_manifest') as mock_manifest:
                mock_manifest.return_value = failing_plugin.metadata
                
                with pytest.raises(PluginLoadError):
                    await plugin_manager.load_plugin("failing-plugin")
                
                # Plugin should not be in loaded plugins
                assert plugin_manager.get_plugin("failing-plugin") is None
