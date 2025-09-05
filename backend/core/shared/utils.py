#!/usr/bin/env python3
"""
Shared Utilities for AlsaniaMCP
Common functions and utilities used across the system
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("alsaniamcp.shared")

def generate_hash(data: str) -> str:
    """Generate SHA256 hash of data"""
    return hashlib.sha256(data.encode()).hexdigest()

def safe_json_dumps(obj: Any) -> str:
    """Safely serialize object to JSON"""
    try:
        return json.dumps(obj, default=str)
    except Exception as e:
        logger.error(f"Failed to serialize object to JSON: {e}")
        return json.dumps({"error": "Serialization failed"})

def safe_json_loads(data: str) -> Optional[Dict]:
    """Safely deserialize JSON string"""
    try:
        return json.loads(data)
    except Exception as e:
        logger.error(f"Failed to deserialize JSON: {e}")
        return None

def format_timestamp(dt: datetime = None) -> str:
    """Format timestamp for consistent use across the system"""
    if dt is None:
        dt = datetime.now()
    return dt.isoformat()

def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format"""
    import re
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_string)) 