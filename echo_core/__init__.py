"""
Echo Core Package

Intelligence system for AlsaniaMCP providing learning,
memory management, and state tracking capabilities.
"""

from . import learning
from . import memory
from . import state

__version__ = "1.0.0"

__all__ = [
    'learning',
    'memory',
    'state'
]