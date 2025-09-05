"""
Pytest configuration and fixtures for AlsaniaMCP tests

Provides common fixtures, test configuration, and setup/teardown
for the entire test suite.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from unittest.mock import Mock, AsyncMock

# Import test utilities
from backend.core.plugins import (
    PluginManager, ServiceContainer, EventBus, ConfigManager
)
from backend.core.imports import get_import_manager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        'plugins': {
            'discovery_paths': ['./tests/fixtures/plugins'],
            'auto_load': False,
            'hot_reload': True,
            'health_check_interval': 5
        },
        'logging': {
            'level': 'DEBUG',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'system': {
            'health_check_interval': 5,
            'max_concurrent_operations': 5
        },
        'database': {
            'url': 'postgresql://test:test@localhost:5432/alsaniamcp_test'
        },
        'redis': {
            'url': 'redis://localhost:6379/1'
        },
        'qdrant': {
            'url': 'http://localhost:6333'
        }
    }


@pytest.fixture
async def service_container():
    """Create a service container for testing"""
    container = ServiceContainer()
    yield container
    container.clear()


@pytest.fixture
async def event_bus():
    """Create an event bus for testing"""
    bus = EventBus()
    yield bus
    bus.clear_handlers()
    bus.clear_history()


@pytest.fixture
async def config_manager(test_config, temp_dir):
    """Create a config manager for testing"""
    manager = ConfigManager()
    
    # Write test config to file
    config_file = temp_dir / "test_config.json"
    import json
    with open(config_file, 'w') as f:
        json.dump(test_config, f)
    
    manager.add_source("test", str(config_file), "json", priority=200)
    await manager.load_all()
    
    yield manager
    await manager.shutdown()


@pytest.fixture
async def plugin_manager(service_container, event_bus, config_manager):
    """Create a plugin manager for testing"""
    manager = PluginManager(service_container, event_bus, config_manager)
    yield manager
    await manager.shutdown()


@pytest.fixture
def mock_database():
    """Mock database connection"""
    mock_db = Mock()
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.fetchval = AsyncMock(return_value=None)
    return mock_db


@pytest.fixture
def mock_redis():
    """Mock Redis connection"""
    mock_redis = Mock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.exists = AsyncMock(return_value=False)
    return mock_redis


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client"""
    mock_qdrant = Mock()
    mock_qdrant.search = AsyncMock(return_value=[])
    mock_qdrant.upsert = AsyncMock(return_value=True)
    mock_qdrant.delete = AsyncMock(return_value=True)
    return mock_qdrant


@pytest.fixture
def sample_plugin_manifest():
    """Sample plugin manifest for testing"""
    return {
        'name': 'test-plugin',
        'version': '1.0.0',
        'type': 'extension',
        'description': 'Test plugin for unit testing',
        'author': 'Test Suite',
        'license': 'MIT',
        'dependencies': [],
        'entry_point': 'test_plugin:TestPlugin',
        'hot_reload': True,
        'priority': 100,
        'configuration': {
            'schema': {
                'test_setting': {
                    'type': 'string',
                    'default': 'test_value',
                    'description': 'Test configuration setting'
                }
            }
        }
    }


@pytest.fixture
def sample_agent_config():
    """Sample agent configuration for testing"""
    return {
        'name': 'test-agent',
        'memory_namespace': 'test_agent',
        'capabilities': ['test', 'mock'],
        'config': {
            'max_memory_size': 1000,
            'response_timeout': 30
        }
    }


@pytest.fixture
def sample_embedding_config():
    """Sample embedding configuration for testing"""
    return {
        'name': 'test-embeddings',
        'dimension': 384,
        'max_input_length': 512,
        'model_type': 'tfidf'
    }


@pytest.fixture
def sample_memory_config():
    """Sample memory configuration for testing"""
    return {
        'name': 'test-memory',
        'storage_type': 'in_memory',
        'max_entries': 1000
    }


@pytest.fixture
async def test_plugin_directory(temp_dir, sample_plugin_manifest):
    """Create a test plugin directory with manifest"""
    plugin_dir = temp_dir / "test_plugin"
    plugin_dir.mkdir()
    
    # Write manifest
    import yaml
    with open(plugin_dir / "plugin.yaml", 'w') as f:
        yaml.dump(sample_plugin_manifest, f)
    
    # Write plugin code
    plugin_code = '''
from backend.core.plugins.interfaces import IPlugin, PluginMetadata, PluginType

class TestPlugin(IPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            plugin_type=PluginType.EXTENSION,
            description="Test plugin"
        )
    
    async def _initialize_impl(self, config):
        self.test_data = config.get('test_setting', 'default')
    
    async def _start_impl(self):
        pass
    
    async def _stop_impl(self):
        pass
    
    async def _health_check_impl(self):
        return True
'''
    
    with open(plugin_dir / "test_plugin.py", 'w') as f:
        f.write(plugin_code)
    
    return plugin_dir


@pytest.fixture
def import_manager():
    """Get the import manager for testing"""
    return get_import_manager()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    # Add custom markers
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "plugin: mark test as a plugin test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "docker: mark test as requiring Docker"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add markers based on test location
    for item in items:
        # Add unit marker for tests in unit/ directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add integration marker for tests in integration/ directory
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add plugin marker for tests in plugins/ directory
        elif "plugins" in str(item.fspath):
            item.add_marker(pytest.mark.plugin)


# Async test utilities
@pytest.fixture
async def async_test_client():
    """Create an async test client for FastAPI testing"""
    from httpx import AsyncClient
    from backend.core.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
