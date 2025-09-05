"""
AlsaniaMCP Plugin System

This module provides the core plugin infrastructure for AlsaniaMCP,
enabling modular, hot-swappable components with standardized interfaces.
"""

from .interfaces import (
    IPlugin,
    IAgentPlugin,
    IEmbeddingPlugin,
    IMemoryPlugin,
    PluginStatus,
    PluginType
)

from .manager import PluginManager
from .container import ServiceContainer
from .events import EventBus
from .config import ConfigManager
from .discovery import PluginDiscovery
from .exceptions import (
    PluginError,
    PluginLoadError,
    PluginDependencyError,
    PluginConfigError
)

__all__ = [
    # Interfaces
    'IPlugin',
    'IAgentPlugin', 
    'IEmbeddingPlugin',
    'IMemoryPlugin',
    'PluginStatus',
    'PluginType',
    
    # Core Components
    'PluginManager',
    'ServiceContainer',
    'EventBus',
    'ConfigManager',
    'PluginDiscovery',
    
    # Exceptions
    'PluginError',
    'PluginLoadError',
    'PluginDependencyError',
    'PluginConfigError'
]

# Version information
__version__ = "1.0.0"
__author__ = "Alsania Team"
