"""
AlsaniaMCP Test Suite

Comprehensive testing infrastructure for the AlsaniaMCP system
including unit tests, integration tests, and plugin testing.
"""

import os
import sys
from pathlib import Path

# Add backend to Python path for testing
backend_root = Path(__file__).parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Test configuration
TEST_CONFIG = {
    'test_db_url': 'postgresql://test:test@localhost:5432/alsaniamcp_test',
    'test_redis_url': 'redis://localhost:6379/1',
    'test_qdrant_url': 'http://localhost:6333',
    'test_data_dir': Path(__file__).parent / 'data',
    'mock_external_services': True
}

__version__ = "1.0.0"

__all__ = [
    'TEST_CONFIG'
]
