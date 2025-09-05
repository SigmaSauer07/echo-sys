"""
AlsaniaMCP Core Package

Core functionality for the AlsaniaMCP system including
authentication, embeddings, memory, and plugin infrastructure.
"""

from .plugins import (
    PluginManager,
    ServiceContainer,
    EventBus,
    ConfigManager,
    IPlugin,
    IAgentPlugin,
    IEmbeddingPlugin,
    IMemoryPlugin
)

# Core modules
from . import auth
from . import embeddings
from . import memory
from . import openai_compat
from . import persistence
from . import snapshots

__version__ = "1.0.0"

__all__ = [
    # Plugin system
    'PluginManager',
    'ServiceContainer', 
    'EventBus',
    'ConfigManager',
    'IPlugin',
    'IAgentPlugin',
    'IEmbeddingPlugin',
    'IMemoryPlugin',
    
    # Core modules
    'auth',
    'embeddings',
    'memory',
    'openai_compat',
    'persistence',
    'snapshots'
]
