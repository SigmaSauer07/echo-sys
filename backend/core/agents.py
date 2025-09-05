"""
Persistent Agent Identity System for AlsaniaMCP
Implements isolated memory namespaces and agent persona management
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import psycopg2
import psycopg2.extras

from config.config import config

logger = logging.getLogger("alsaniamcp.agents")

class AgentManager:
    """Manages persistent agent identities and memory namespaces"""
    
    def __init__(self):
        self.postgres_url = config.POSTGRES_URL
        self._ensure_agent_tables()
    
    def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(
            self.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    
    def _ensure_agent_tables(self):
        """Ensure agent management tables exist"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Enhanced agent_identities table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS agents.agent_identities (
                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            agent_name VARCHAR(255) UNIQUE NOT NULL,
                            display_name VARCHAR(255) NOT NULL,
                            description TEXT,
                            persona_metadata JSONB DEFAULT '{}',
                            memory_namespace VARCHAR(255) UNIQUE NOT NULL,
                            api_key_id UUID REFERENCES alsania.api_keys(id),
                            is_active BOOLEAN DEFAULT true,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            last_active TIMESTAMP WITH TIME ZONE,
                            memory_count BIGINT DEFAULT 0,
                            created_by VARCHAR(255) DEFAULT 'system'
                        )
                    """)
                    
                    # Agent memory isolation table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS agents.agent_memories (
                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            agent_id UUID REFERENCES agents.agent_identities(id) ON DELETE CASCADE,
                            memory_id UUID REFERENCES memory.memories(id) ON DELETE CASCADE,
                            access_level VARCHAR(50) DEFAULT 'private',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            UNIQUE(agent_id, memory_id)
                        )
                    """)
                    
                    # Agent sessions table for tracking activity
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS agents.agent_sessions (
                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            agent_id UUID REFERENCES agents.agent_identities(id) ON DELETE CASCADE,
                            session_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            session_end TIMESTAMP WITH TIME ZONE,
                            activity_count INTEGER DEFAULT 0,
                            metadata JSONB DEFAULT '{}'
                        )
                    """)
                    
                    # Create indexes for performance
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_agent_identities_namespace 
                        ON agents.agent_identities(memory_namespace)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_agent_memories_agent 
                        ON agents.agent_memories(agent_id)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_agent_sessions_agent 
                        ON agents.agent_sessions(agent_id)
                    """)
                    
                    # Update trigger for agent_identities
                    cur.execute("""
                        CREATE OR REPLACE FUNCTION update_agent_updated_at()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            NEW.updated_at = NOW();
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql;
                    """)
                    
                    cur.execute("""
                        DROP TRIGGER IF EXISTS trigger_update_agent_updated_at ON agents.agent_identities;
                        CREATE TRIGGER trigger_update_agent_updated_at
                            BEFORE UPDATE ON agents.agent_identities
                            FOR EACH ROW EXECUTE FUNCTION update_agent_updated_at();
                    """)
                    
                    conn.commit()
                    logger.info("✅ Agent management tables initialized")
                    
        except Exception as e:
            logger.error(f"Failed to initialize agent tables: {e}")
            raise
    
    def create_agent(self, agent_name: str, display_name: str, description: str = "", 
                    persona_metadata: Dict = None, api_key_id: str = None) -> Dict:
        """Create a new agent identity with isolated memory namespace"""
        
        if not persona_metadata:
            persona_metadata = {}
        
        # Generate unique memory namespace
        memory_namespace = f"agent_{agent_name.lower().replace(' ', '_')}_{str(uuid.uuid4())[:8]}"
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Check if agent name already exists
                    cur.execute("""
                        SELECT id FROM agents.agent_identities 
                        WHERE agent_name = %s
                    """, (agent_name,))
                    
                    if cur.fetchone():
                        raise ValueError(f"Agent name '{agent_name}' already exists")
                    
                    # Create agent identity
                    cur.execute("""
                        INSERT INTO agents.agent_identities 
                        (agent_name, display_name, description, persona_metadata, 
                         memory_namespace, api_key_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                    """, (
                        agent_name, display_name, description,
                        json.dumps(persona_metadata), memory_namespace, api_key_id
                    ))
                    
                    result = cur.fetchone()
                    agent_id = result['id']
                    
                    # Create initial session
                    cur.execute("""
                        INSERT INTO agents.agent_sessions (agent_id, metadata)
                        VALUES (%s, %s)
                        RETURNING id
                    """, (agent_id, json.dumps({"creation_session": True})))
                    
                    session_id = cur.fetchone()['id']
                    
                    conn.commit()
                    
                    logger.info(f"✅ Created agent: {agent_name} (namespace: {memory_namespace})")
                    
                    return {
                        'id': agent_id,
                        'agent_name': agent_name,
                        'display_name': display_name,
                        'description': description,
                        'persona_metadata': persona_metadata,
                        'memory_namespace': memory_namespace,
                        'created_at': result['created_at'].isoformat(),
                        'session_id': session_id
                    }
                    
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise
    
    def get_agent(self, agent_id: str = None, agent_name: str = None, 
                  memory_namespace: str = None) -> Optional[Dict]:
        """Get agent by ID, name, or memory namespace"""
        
        if not any([agent_id, agent_name, memory_namespace]):
            raise ValueError("Must provide agent_id, agent_name, or memory_namespace")
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    if agent_id:
                        condition = "id = %s"
                        value = agent_id
                    elif agent_name:
                        condition = "agent_name = %s"
                        value = agent_name
                    else:
                        condition = "memory_namespace = %s"
                        value = memory_namespace
                    
                    cur.execute(f"""
                        SELECT id, agent_name, display_name, description, 
                               persona_metadata, memory_namespace, api_key_id,
                               is_active, created_at, updated_at, last_active, memory_count
                        FROM agents.agent_identities 
                        WHERE {condition} AND is_active = true
                    """, (value,))
                    
                    result = cur.fetchone()
                    if not result:
                        return None
                    
                    return {
                        'id': result['id'],
                        'agent_name': result['agent_name'],
                        'display_name': result['display_name'],
                        'description': result['description'],
                        'persona_metadata': result['persona_metadata'],
                        'memory_namespace': result['memory_namespace'],
                        'api_key_id': result['api_key_id'],
                        'is_active': result['is_active'],
                        'created_at': result['created_at'].isoformat() if result['created_at'] else None,
                        'updated_at': result['updated_at'].isoformat() if result['updated_at'] else None,
                        'last_active': result['last_active'].isoformat() if result['last_active'] else None,
                        'memory_count': result['memory_count']
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get agent: {e}")
            return None
    
    def list_agents(self, api_key_id: str = None, include_inactive: bool = False) -> List[Dict]:
        """List all agents, optionally filtered by API key"""
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    conditions = []
                    params = []
                    
                    if not include_inactive:
                        conditions.append("is_active = true")
                    
                    if api_key_id:
                        conditions.append("api_key_id = %s")
                        params.append(api_key_id)
                    
                    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
                    
                    cur.execute(f"""
                        SELECT id, agent_name, display_name, description, 
                               persona_metadata, memory_namespace, api_key_id,
                               is_active, created_at, updated_at, last_active, memory_count
                        FROM agents.agent_identities 
                        {where_clause}
                        ORDER BY created_at DESC
                    """, params)
                    
                    results = cur.fetchall()
                    
                    return [
                        {
                            'id': row['id'],
                            'agent_name': row['agent_name'],
                            'display_name': row['display_name'],
                            'description': row['description'],
                            'persona_metadata': row['persona_metadata'],
                            'memory_namespace': row['memory_namespace'],
                            'api_key_id': row['api_key_id'],
                            'is_active': row['is_active'],
                            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                            'last_active': row['last_active'].isoformat() if row['last_active'] else None,
                            'memory_count': row['memory_count']
                        }
                        for row in results
                    ]
                    
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []
    
    def update_agent_activity(self, agent_id: str) -> bool:
        """Update agent's last activity timestamp"""
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE agents.agent_identities 
                        SET last_active = NOW()
                        WHERE id = %s
                    """, (agent_id,))
                    
                    conn.commit()
                    return cur.rowcount > 0
                    
        except Exception as e:
            logger.error(f"Failed to update agent activity: {e}")
            return False
    
    def associate_memory_with_agent(self, agent_id: str, memory_id: str, 
                                   access_level: str = "private") -> bool:
        """Associate a memory with an agent's namespace"""
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Insert association
                    cur.execute("""
                        INSERT INTO agents.agent_memories (agent_id, memory_id, access_level)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (agent_id, memory_id) DO UPDATE SET
                            access_level = EXCLUDED.access_level
                    """, (agent_id, memory_id, access_level))
                    
                    # Update memory count
                    cur.execute("""
                        UPDATE agents.agent_identities 
                        SET memory_count = (
                            SELECT COUNT(*) FROM agents.agent_memories 
                            WHERE agent_id = %s
                        )
                        WHERE id = %s
                    """, (agent_id, agent_id))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to associate memory with agent: {e}")
            return False
    
    def get_agent_memories(self, agent_id: str, access_level: str = None) -> List[Dict]:
        """Get all memories associated with an agent"""
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    conditions = ["am.agent_id = %s"]
                    params = [agent_id]
                    
                    if access_level:
                        conditions.append("am.access_level = %s")
                        params.append(access_level)
                    
                    where_clause = " AND ".join(conditions)
                    
                    cur.execute(f"""
                        SELECT m.id, m.content, m.source, m.metadata, m.created_at,
                               am.access_level, am.created_at as associated_at
                        FROM memory.memories m
                        JOIN agents.agent_memories am ON m.id = am.memory_id
                        WHERE {where_clause}
                        ORDER BY am.created_at DESC
                    """, params)
                    
                    results = cur.fetchall()
                    
                    return [
                        {
                            'id': row['id'],
                            'content': row['content'],
                            'source': row['source'],
                            'metadata': row['metadata'],
                            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                            'access_level': row['access_level'],
                            'associated_at': row['associated_at'].isoformat() if row['associated_at'] else None
                        }
                        for row in results
                    ]
                    
        except Exception as e:
            logger.error(f"Failed to get agent memories: {e}")
            return []

# Global agent manager instance
agent_manager = AgentManager()
