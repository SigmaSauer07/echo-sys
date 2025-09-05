"""
Snapshot Manager Package

IPFS-backed storage and integrity verification system for AlsaniaMCP.
"""

from . import backups
from . import integrity

__version__ = "1.0.0"

__all__ = [
    'backups',
    'integrity'
]
