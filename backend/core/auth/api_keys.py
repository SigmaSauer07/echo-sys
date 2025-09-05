"""
Authentication & Rate Limiting Module for AlsaniaMCP
Implements production-grade API key management and abuse prevention
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
import psycopg2
import psycopg2.extras
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.config import config

logger = logging.getLogger("alsaniamcp.auth")

class RateLimiter:
    """Token bucket rate limiter with sliding window"""
    
    def __init__(self):
        self.buckets = defaultdict(lambda: {
            'tokens': 100,  # Default tokens
            'last_refill': time.time(),
            'requests': deque()  # For sliding window
        })
        self.default_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'burst_limit': 100
        }
    
    def is_allowed(self, api_key: str, limits: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Check if request is allowed under rate limits"""
        if not limits:
            limits = self.default_limits
        
        current_time = time.time()
        bucket = self.buckets[api_key]
        
        # Clean old requests (sliding window)
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        # Remove requests older than 1 hour
        while bucket['requests'] and bucket['requests'][0] < hour_ago:
            bucket['requests'].popleft()
        
        # Count requests in last minute and hour
        requests_last_minute = sum(1 for req_time in bucket['requests'] if req_time > minute_ago)
        requests_last_hour = len(bucket['requests'])
        
        # Check limits
        if requests_last_minute >= limits['requests_per_minute']:
            return False, {
                'error': 'Rate limit exceeded: too many requests per minute',
                'retry_after': 60 - (current_time - minute_ago),
                'limits': limits
            }
        
        if requests_last_hour >= limits['requests_per_hour']:
            return False, {
                'error': 'Rate limit exceeded: too many requests per hour',
                'retry_after': 3600 - (current_time - hour_ago),
                'limits': limits
            }
        
        # Token bucket for burst protection
        time_passed = current_time - bucket['last_refill']
        bucket['tokens'] = min(
            limits['burst_limit'],
            bucket['tokens'] + time_passed * (limits['requests_per_minute'] / 60)
        )
        bucket['last_refill'] = current_time
        
        if bucket['tokens'] < 1:
            return False, {
                'error': 'Rate limit exceeded: burst limit reached',
                'retry_after': 1,
                'limits': limits
            }
        
        # Allow request
        bucket['tokens'] -= 1
        bucket['requests'].append(current_time)
        
        return True, {
            'remaining_tokens': int(bucket['tokens']),
            'requests_last_minute': requests_last_minute + 1,
            'requests_last_hour': requests_last_hour + 1,
            'limits': limits
        }

class APIKeyManager:
    """Enhanced API key manager with multi-tier permissions and quotas"""

    # API Key Tiers
    TIER_ADMIN = "admin"
    TIER_TEAM = "team"
    TIER_USER = "user"

    # Default permissions by tier
    DEFAULT_PERMISSIONS = {
        TIER_ADMIN: {
            "admin": True, "read": True, "write": True, "manage_keys": True,
            "manage_agents": True, "manage_snapshots": True, "system_config": True
        },
        TIER_TEAM: {
            "read": True, "write": True, "manage_agents": True, "manage_snapshots": True,
            "namespace_isolation": True
        },
        TIER_USER: {
            "read": True, "write": False, "namespace_isolation": True, "restricted_agents": True
        }
    }

    # Default quotas by tier
    DEFAULT_QUOTAS = {
        TIER_ADMIN: {
            "max_agents": -1,  # Unlimited
            "max_memories_per_agent": -1,
            "max_snapshots": -1,
            "requests_per_minute": 1000,
            "requests_per_hour": 50000,
            "requests_per_day": 1000000,
            "burst_limit": 500
        },
        TIER_TEAM: {
            "max_agents": 50,
            "max_memories_per_agent": 10000,
            "max_snapshots": 100,
            "requests_per_minute": 200,
            "requests_per_hour": 10000,
            "requests_per_day": 100000,
            "burst_limit": 300
        },
        TIER_USER: {
            "max_agents": 5,
            "max_memories_per_agent": 1000,
            "max_snapshots": 10,
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "requests_per_day": 10000,
            "burst_limit": 100
        }
    }

    def __init__(self):
        self.postgres_url = config.POSTGRES_URL
        self._ensure_api_keys_table()

    def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(
            self.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    def _ensure_api_keys_table(self):
        """Ensure enhanced API keys table exists"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Create enhanced API keys table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS alsania.api_keys (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            key_hash VARCHAR(128) UNIQUE NOT NULL,
                            key_prefix VARCHAR(20) NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            tier VARCHAR(20) NOT NULL DEFAULT 'user',
                            permissions JSONB DEFAULT '{}',
                            quotas JSONB DEFAULT '{}',
                            rate_limits JSONB DEFAULT '{}',
                            namespaces TEXT[] DEFAULT '{}',
                            allowed_agents TEXT[] DEFAULT '{}',
                            expires_at TIMESTAMP WITH TIME ZONE,
                            is_active BOOLEAN DEFAULT true,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            last_used TIMESTAMP WITH TIME ZONE,
                            usage_count BIGINT DEFAULT 0,
                            created_by VARCHAR(255) DEFAULT 'system',
                            metadata JSONB DEFAULT '{}'
                        )
                    """)

                    # Create usage tracking table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS alsania.api_key_usage (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            api_key_id UUID REFERENCES alsania.api_keys(id) ON DELETE CASCADE,
                            date DATE DEFAULT CURRENT_DATE,
                            requests_count BIGINT DEFAULT 0,
                            agents_created INTEGER DEFAULT 0,
                            memories_stored INTEGER DEFAULT 0,
                            snapshots_created INTEGER DEFAULT 0,
                            last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            UNIQUE(api_key_id, date)
                        )
                    """)

                    # Create indexes for performance
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_api_keys_hash
                        ON alsania.api_keys(key_hash)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_api_keys_tier
                        ON alsania.api_keys(tier)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_api_key_usage_date
                        ON alsania.api_key_usage(api_key_id, date)
                    """)

                    # Insert default development key if not exists
                    dev_key_hash = hashlib.sha256("alsania-dev".encode()).hexdigest()
                    cur.execute("""
                        INSERT INTO alsania.api_keys
                        (key_hash, key_prefix, name, description, tier, permissions, quotas, rate_limits)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (key_hash) DO NOTHING
                    """, (
                        dev_key_hash,
                        "alsania-dev",
                        "Development Key",
                        "Default development API key with admin privileges",
                        self.TIER_ADMIN,
                        json.dumps(self.DEFAULT_PERMISSIONS[self.TIER_ADMIN]),
                        json.dumps(self.DEFAULT_QUOTAS[self.TIER_ADMIN]),
                        json.dumps(self.DEFAULT_QUOTAS[self.TIER_ADMIN])
                    ))

                    conn.commit()
                    logger.info("✅ Enhanced API keys table initialized")

        except Exception as e:
            logger.error(f"Failed to initialize API keys table: {e}")
            raise
    
    def validate_api_key(self, api_key: str) -> Optional[Dict]:
        """Validate API key and return enhanced key info"""
        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, tier, permissions, quotas, rate_limits,
                               namespaces, allowed_agents, expires_at, is_active,
                               usage_count, metadata
                        FROM alsania.api_keys
                        WHERE key_hash = %s AND is_active = true
                        AND (expires_at IS NULL OR expires_at > NOW())
                    """, (key_hash,))

                    result = cur.fetchone()
                    if not result:
                        return None

                    # Update last used timestamp and usage count
                    cur.execute("""
                        UPDATE alsania.api_keys
                        SET last_used = NOW(), usage_count = usage_count + 1
                        WHERE key_hash = %s
                    """, (key_hash,))

                    # Update daily usage tracking
                    cur.execute("""
                        INSERT INTO alsania.api_key_usage (api_key_id, requests_count)
                        VALUES (%s, 1)
                        ON CONFLICT (api_key_id, date)
                        DO UPDATE SET
                            requests_count = api_key_usage.requests_count + 1,
                            last_updated = NOW()
                    """, (result['id'],))

                    conn.commit()

                    return {
                        'id': result['id'],
                        'name': result['name'],
                        'tier': result['tier'],
                        'permissions': result['permissions'] or {},
                        'quotas': result['quotas'] or {},
                        'rate_limits': result['rate_limits'] or {},
                        'namespaces': result['namespaces'] or [],
                        'allowed_agents': result['allowed_agents'] or [],
                        'usage_count': result['usage_count'] + 1,
                        'metadata': result['metadata'] or {}
                    }

        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return None
    
    def create_api_key(self, name: str, tier: str = None, description: str = "",
                      permissions: Dict = None, quotas: Dict = None,
                      namespaces: List[str] = None, allowed_agents: List[str] = None,
                      expires_days: int = None, created_by: str = "admin") -> Dict:
        """Create a new API key with enhanced features"""
        import secrets
        from datetime import datetime, timedelta

        # Validate tier
        if not tier:
            tier = self.TIER_USER
        if tier not in [self.TIER_ADMIN, self.TIER_TEAM, self.TIER_USER]:
            raise ValueError(f"Invalid tier: {tier}")

        # Generate secure API key with tier prefix
        tier_prefix = {"admin": "ak_admin", "team": "ak_team", "user": "ak_user"}[tier]
        api_key = f"{tier_prefix}_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:15] + "..."

        # Set default permissions and quotas based on tier
        if not permissions:
            permissions = self.DEFAULT_PERMISSIONS[tier].copy()
        if not quotas:
            quotas = self.DEFAULT_QUOTAS[tier].copy()

        # Set expiration if specified
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)

        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO alsania.api_keys
                        (key_hash, key_prefix, name, description, tier, permissions,
                         quotas, rate_limits, namespaces, allowed_agents, expires_at, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                    """, (
                        key_hash, key_prefix, name, description, tier,
                        json.dumps(permissions), json.dumps(quotas), json.dumps(quotas),
                        namespaces or [], allowed_agents or [], expires_at, created_by
                    ))

                    result = cur.fetchone()
                    conn.commit()

                    logger.info(f"✅ Created {tier} API key: {name} ({key_prefix})")

                    return {
                        'id': result['id'],
                        'api_key': api_key,  # Only returned once!
                        'name': name,
                        'tier': tier,
                        'permissions': permissions,
                        'quotas': quotas,
                        'namespaces': namespaces or [],
                        'allowed_agents': allowed_agents or [],
                        'expires_at': expires_at.isoformat() if expires_at else None,
                        'created_at': result['created_at'].isoformat()
                    }

        except Exception as e:
            logger.error(f"Failed to create API key: {e}")
            raise
    
    def list_api_keys(self) -> List[Dict]:
        """List all API keys (without the actual keys)"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, key_prefix, name, description, permissions, 
                               rate_limits, is_active, created_at, last_used, usage_count
                        FROM alsania.api_keys 
                        ORDER BY created_at DESC
                    """)
                    
                    results = cur.fetchall()
                    
                    return [
                        {
                            'id': row['id'],
                            'key_prefix': row['key_prefix'],
                            'name': row['name'],
                            'description': row['description'],
                            'permissions': row['permissions'],
                            'rate_limits': row['rate_limits'],
                            'is_active': row['is_active'],
                            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                            'last_used': row['last_used'].isoformat() if row['last_used'] else None,
                            'usage_count': row['usage_count']
                        }
                        for row in results
                    ]
                    
        except Exception as e:
            logger.error(f"Failed to list API keys: {e}")
            return []
    
    def check_quota(self, api_key_id: str, quota_type: str, increment: int = 1) -> Tuple[bool, Dict]:
        """Check if API key is within quota limits"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Get key quotas
                    cur.execute("""
                        SELECT quotas, tier FROM alsania.api_keys WHERE id = %s
                    """, (api_key_id,))

                    key_result = cur.fetchone()
                    if not key_result:
                        return False, {"error": "API key not found"}

                    quotas = key_result['quotas'] or {}
                    tier = key_result['tier']

                    # Get current usage
                    cur.execute("""
                        SELECT agents_created, memories_stored, snapshots_created
                        FROM alsania.api_key_usage
                        WHERE api_key_id = %s AND date = CURRENT_DATE
                    """, (api_key_id,))

                    usage_result = cur.fetchone()
                    current_usage = {
                        'agents_created': usage_result['agents_created'] if usage_result else 0,
                        'memories_stored': usage_result['memories_stored'] if usage_result else 0,
                        'snapshots_created': usage_result['snapshots_created'] if usage_result else 0
                    }

                    # Check specific quota
                    quota_map = {
                        'agents': ('max_agents', 'agents_created'),
                        'memories': ('max_memories_per_agent', 'memories_stored'),
                        'snapshots': ('max_snapshots', 'snapshots_created')
                    }

                    if quota_type in quota_map:
                        quota_key, usage_key = quota_map[quota_type]
                        max_allowed = quotas.get(quota_key, self.DEFAULT_QUOTAS[tier][quota_key])
                        current_count = current_usage[usage_key]

                        # -1 means unlimited
                        if max_allowed != -1 and current_count + increment > max_allowed:
                            return False, {
                                "error": f"Quota exceeded for {quota_type}",
                                "current": current_count,
                                "limit": max_allowed,
                                "tier": tier
                            }

                    return True, {
                        "quota_type": quota_type,
                        "current_usage": current_usage,
                        "quotas": quotas,
                        "tier": tier
                    }

        except Exception as e:
            logger.error(f"Quota check failed: {e}")
            return False, {"error": str(e)}

    def update_usage(self, api_key_id: str, usage_type: str, increment: int = 1) -> bool:
        """Update usage statistics for an API key"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    usage_columns = {
                        'agents': 'agents_created',
                        'memories': 'memories_stored',
                        'snapshots': 'snapshots_created'
                    }

                    if usage_type not in usage_columns:
                        return False

                    column = usage_columns[usage_type]
                    cur.execute(f"""
                        INSERT INTO alsania.api_key_usage (api_key_id, {column})
                        VALUES (%s, %s)
                        ON CONFLICT (api_key_id, date)
                        DO UPDATE SET
                            {column} = api_key_usage.{column} + %s,
                            last_updated = NOW()
                    """, (api_key_id, increment, increment))

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Usage update failed: {e}")
            return False

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE alsania.api_keys
                        SET is_active = false
                        WHERE id = %s
                    """, (key_id,))

                    conn.commit()

                    if cur.rowcount > 0:
                        logger.info(f"✅ Revoked API key: {key_id}")
                        return True
                    else:
                        logger.warning(f"API key not found: {key_id}")
                        return False

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return False

class AuthenticationManager:
    """Main authentication manager combining API keys and rate limiting"""

    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.rate_limiter = RateLimiter()
        self.security = HTTPBearer()
    
    async def authenticate_request(self, request: Request, credentials: HTTPAuthorizationCredentials) -> Dict:
        """Authenticate and authorize a request"""
        api_key = credentials.credentials
        
        # Validate API key
        key_info = self.api_key_manager.validate_api_key(api_key)
        if not key_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired API key"
            )
        
        # Check rate limits
        rate_limits = key_info.get('rate_limits', {})
        allowed, rate_info = self.rate_limiter.is_allowed(api_key, rate_limits)
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=rate_info['error'],
                headers={"Retry-After": str(int(rate_info['retry_after']))}
            )
        
        # Add rate limit headers to response (will be handled by middleware)
        request.state.rate_limit_info = rate_info
        request.state.api_key_info = key_info
        
        return key_info
    
    def check_permission(self, key_info: Dict, required_permission: str) -> bool:
        """Check if API key has required permission"""
        permissions = key_info.get('permissions', {})
        
        # Admin permission grants all access
        if permissions.get('admin', False):
            return True
        
        return permissions.get(required_permission, False)

# Global authentication manager
auth_manager = AuthenticationManager()
