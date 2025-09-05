"""
Snapshot Manager System for AlsaniaMCP
Implements agent memory state saving and rollback functionality
"""

import json
import logging
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import psycopg2
import psycopg2.extras

from config.config import config

logger = logging.getLogger("alsaniamcp.snapshots")

class SnapshotManager:
    """Manages agent memory state snapshots and rollback functionality"""
    
    def __init__(self):
        self.postgres_url = config.POSTGRES_URL
        self.snapshots_dir = Path("snapshots")
        self.snapshots_dir.mkdir(exist_ok=True)
        self._ensure_snapshot_tables()
    
    def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(
            self.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    
    def _ensure_snapshot_tables(self):
        """Ensure snapshot management tables exist"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Enhanced snapshots table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS memory.agent_snapshots (
                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            snapshot_name VARCHAR(255) NOT NULL,
                            agent_id UUID REFERENCES agents.agent_identities(id) ON DELETE CASCADE,
                            description TEXT,
                            snapshot_type VARCHAR(50) DEFAULT 'manual',
                            memory_count INTEGER DEFAULT 0,
                            vector_count INTEGER DEFAULT 0,
                            data_hash VARCHAR(128),
                            file_path TEXT,
                            metadata JSONB DEFAULT '{}',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            created_by VARCHAR(255) DEFAULT 'system',
                            is_active BOOLEAN DEFAULT true,
                            UNIQUE(agent_id, snapshot_name)
                        )
                    """)
                    
                    # Snapshot restore history
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS memory.snapshot_restores (
                            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            snapshot_id UUID REFERENCES memory.agent_snapshots(id) ON DELETE CASCADE,
                            agent_id UUID REFERENCES agents.agent_identities(id) ON DELETE CASCADE,
                            restore_type VARCHAR(50) DEFAULT 'full',
                            restored_memories INTEGER DEFAULT 0,
                            restored_vectors INTEGER DEFAULT 0,
                            success BOOLEAN DEFAULT false,
                            error_message TEXT,
                            metadata JSONB DEFAULT '{}',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            created_by VARCHAR(255) DEFAULT 'system'
                        )
                    """)
                    
                    # Create indexes
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_agent_snapshots_agent 
                        ON memory.agent_snapshots(agent_id)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_agent_snapshots_created 
                        ON memory.agent_snapshots(created_at)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_snapshot_restores_snapshot 
                        ON memory.snapshot_restores(snapshot_id)
                    """)
                    
                    conn.commit()
                    logger.info("✅ Snapshot management tables initialized")
                    
        except Exception as e:
            logger.error(f"Failed to initialize snapshot tables: {e}")
            raise
    
    def create_agent_snapshot(self, agent_id: str, snapshot_name: str, 
                             description: str = "", snapshot_type: str = "manual",
                             created_by: str = "system") -> Dict:
        """Create a comprehensive snapshot of an agent's memory state"""
        
        try:
            # Get agent info
            from core.agents import agent_manager
            agent = agent_manager.get_agent(agent_id=agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")
            
            # Get agent memories
            agent_memories = agent_manager.get_agent_memories(agent_id)
            
            # Get vector data from Qdrant
            from memory.vector_store import VectorStore
            from config.config import config
            
            qdrant_url = config.QDRANT_URL
            if qdrant_url.startswith('http://'):
                host = qdrant_url.replace('http://', '').split(':')[0]
                port = int(qdrant_url.split(':')[-1]) if ':' in qdrant_url.split('//')[1] else 6333
            else:
                host = 'localhost'
                port = 6333
            
            vector_store = VectorStore(host=host, port=port)
            
            # Create snapshot data structure
            snapshot_data = {
                "agent_info": agent,
                "memories": agent_memories,
                "vectors": [],
                "metadata": {
                    "snapshot_name": snapshot_name,
                    "description": description,
                    "snapshot_type": snapshot_type,
                    "created_by": created_by,
                    "created_at": datetime.now().isoformat(),
                    "memory_count": len(agent_memories),
                    "vector_count": 0
                }
            }
            
            # Get vector data for agent memories
            if vector_store.connected:
                try:
                    # Get all points from collection with agent namespace filter
                    points = vector_store.client.scroll(
                        collection_name=vector_store.collection,
                        scroll_filter={
                            "must": [
                                {
                                    "key": "agent_namespace",
                                    "match": {"value": agent["memory_namespace"]}
                                }
                            ]
                        },
                        limit=10000,
                        with_payload=True,
                        with_vectors=True
                    )
                    
                    snapshot_data["vectors"] = [
                        {
                            "id": point.id,
                            "vector": point.vector,
                            "payload": point.payload
                        }
                        for point in points[0]
                    ]
                    
                    snapshot_data["metadata"]["vector_count"] = len(snapshot_data["vectors"])
                    
                except Exception as e:
                    logger.warning(f"Failed to get vector data for snapshot: {e}")
            
            # Generate data hash
            data_str = json.dumps(snapshot_data, sort_keys=True)
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()
            
            # Save snapshot to file
            snapshot_filename = f"agent_{agent_id}_{snapshot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            snapshot_path = self.snapshots_dir / snapshot_filename
            
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot_data, f, indent=2)
            
            # Save snapshot metadata to database
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO memory.agent_snapshots 
                        (snapshot_name, agent_id, description, snapshot_type, 
                         memory_count, vector_count, data_hash, file_path, 
                         metadata, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                    """, (
                        snapshot_name, agent_id, description, snapshot_type,
                        len(agent_memories), len(snapshot_data["vectors"]),
                        data_hash, str(snapshot_path),
                        json.dumps(snapshot_data["metadata"]), created_by
                    ))
                    
                    result = cur.fetchone()
                    snapshot_id = result['id']
                    
                    conn.commit()
                    
                    logger.info(f"✅ Created snapshot: {snapshot_name} for agent {agent_id}")
                    
                    return {
                        'id': snapshot_id,
                        'snapshot_name': snapshot_name,
                        'agent_id': agent_id,
                        'description': description,
                        'snapshot_type': snapshot_type,
                        'memory_count': len(agent_memories),
                        'vector_count': len(snapshot_data["vectors"]),
                        'data_hash': data_hash,
                        'file_path': str(snapshot_path),
                        'created_at': result['created_at'].isoformat(),
                        'created_by': created_by
                    }
                    
        except Exception as e:
            logger.error(f"Failed to create agent snapshot: {e}")
            raise
    
    def list_agent_snapshots(self, agent_id: str = None, include_inactive: bool = False) -> List[Dict]:
        """List snapshots for an agent or all snapshots"""
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    conditions = []
                    params = []
                    
                    if agent_id:
                        conditions.append("agent_id = %s")
                        params.append(agent_id)
                    
                    if not include_inactive:
                        conditions.append("s.is_active = true")
                    
                    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
                    
                    cur.execute(f"""
                        SELECT s.id, s.snapshot_name, s.agent_id, s.description, 
                               s.snapshot_type, s.memory_count, s.vector_count,
                               s.data_hash, s.file_path, s.metadata, s.created_at, 
                               s.created_by, s.is_active,
                               a.agent_name, a.display_name
                        FROM memory.agent_snapshots s
                        LEFT JOIN agents.agent_identities a ON s.agent_id = a.id
                        {where_clause}
                        ORDER BY s.created_at DESC
                    """, params)
                    
                    results = cur.fetchall()
                    
                    return [
                        {
                            'id': row['id'],
                            'snapshot_name': row['snapshot_name'],
                            'agent_id': row['agent_id'],
                            'agent_name': row['agent_name'],
                            'agent_display_name': row['display_name'],
                            'description': row['description'],
                            'snapshot_type': row['snapshot_type'],
                            'memory_count': row['memory_count'],
                            'vector_count': row['vector_count'],
                            'data_hash': row['data_hash'],
                            'file_path': row['file_path'],
                            'metadata': row['metadata'],
                            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                            'created_by': row['created_by'],
                            'is_active': row['is_active']
                        }
                        for row in results
                    ]
                    
        except Exception as e:
            logger.error(f"Failed to list agent snapshots: {e}")
            return []
    
    def restore_agent_snapshot(self, snapshot_id: str, restore_type: str = "full",
                              created_by: str = "system") -> Dict:
        """Restore an agent's memory state from a snapshot"""
        
        try:
            # Get snapshot info
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, snapshot_name, agent_id, file_path, data_hash
                        FROM memory.agent_snapshots 
                        WHERE id = %s AND is_active = true
                    """, (snapshot_id,))
                    
                    snapshot = cur.fetchone()
                    if not snapshot:
                        raise ValueError(f"Snapshot not found: {snapshot_id}")
            
            # Load snapshot data
            snapshot_path = Path(snapshot['file_path'])
            if not snapshot_path.exists():
                raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
            
            with open(snapshot_path, 'r') as f:
                snapshot_data = json.load(f)
            
            # Verify data integrity
            data_str = json.dumps(snapshot_data, sort_keys=True)
            current_hash = hashlib.sha256(data_str.encode()).hexdigest()
            
            if current_hash != snapshot['data_hash']:
                raise ValueError("Snapshot data integrity check failed")
            
            agent_id = snapshot['agent_id']
            restored_memories = 0
            restored_vectors = 0
            
            # Clear existing agent data if full restore
            if restore_type == "full":
                # Clear agent memories
                with self.get_postgres_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            DELETE FROM agents.agent_memories WHERE agent_id = %s
                        """, (agent_id,))
                        conn.commit()
                
                # Clear vectors from Qdrant
                from memory.vector_store import VectorStore
                from config.config import config
                
                qdrant_url = config.QDRANT_URL
                if qdrant_url.startswith('http://'):
                    host = qdrant_url.replace('http://', '').split(':')[0]
                    port = int(qdrant_url.split(':')[-1]) if ':' in qdrant_url.split('//')[1] else 6333
                else:
                    host = 'localhost'
                    port = 6333
                
                vector_store = VectorStore(host=host, port=port)
                
                if vector_store.connected:
                    try:
                        # Delete vectors with agent namespace
                        agent_namespace = snapshot_data["agent_info"]["memory_namespace"]
                        vector_store.client.delete(
                            collection_name=vector_store.collection,
                            points_selector={
                                "filter": {
                                    "must": [
                                        {
                                            "key": "agent_namespace",
                                            "match": {"value": agent_namespace}
                                        }
                                    ]
                                }
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to clear vectors during restore: {e}")
            
            # Restore memories
            from core.agents import agent_manager
            
            for memory in snapshot_data["memories"]:
                try:
                    # Associate memory with agent
                    success = agent_manager.associate_memory_with_agent(
                        agent_id, memory["id"], memory.get("access_level", "private")
                    )
                    if success:
                        restored_memories += 1
                except Exception as e:
                    logger.warning(f"Failed to restore memory {memory['id']}: {e}")
            
            # Restore vectors
            if vector_store.connected:
                for vector_data in snapshot_data["vectors"]:
                    try:
                        vector_store.client.upsert(
                            collection_name=vector_store.collection,
                            points=[{
                                "id": vector_data["id"],
                                "vector": vector_data["vector"],
                                "payload": vector_data["payload"]
                            }]
                        )
                        restored_vectors += 1
                    except Exception as e:
                        logger.warning(f"Failed to restore vector {vector_data['id']}: {e}")
            
            # Record restore operation
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO memory.snapshot_restores 
                        (snapshot_id, agent_id, restore_type, restored_memories, 
                         restored_vectors, success, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                    """, (
                        snapshot_id, agent_id, restore_type, restored_memories,
                        restored_vectors, True, created_by
                    ))
                    
                    result = cur.fetchone()
                    conn.commit()
                    
                    logger.info(f"✅ Restored snapshot: {snapshot['snapshot_name']} for agent {agent_id}")
                    
                    return {
                        'restore_id': result['id'],
                        'snapshot_id': snapshot_id,
                        'agent_id': agent_id,
                        'restore_type': restore_type,
                        'restored_memories': restored_memories,
                        'restored_vectors': restored_vectors,
                        'success': True,
                        'created_at': result['created_at'].isoformat(),
                        'created_by': created_by
                    }
                    
        except Exception as e:
            logger.error(f"Failed to restore agent snapshot: {e}")
            
            # Record failed restore
            try:
                with self.get_postgres_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO memory.snapshot_restores 
                            (snapshot_id, agent_id, restore_type, success, error_message, created_by)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (snapshot_id, agent_id, restore_type, False, str(e), created_by))
                        conn.commit()
            except:
                pass
            
            raise
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot (mark as inactive and optionally remove file)"""
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Get snapshot file path
                    cur.execute("""
                        SELECT file_path FROM memory.agent_snapshots 
                        WHERE id = %s
                    """, (snapshot_id,))
                    
                    result = cur.fetchone()
                    if not result:
                        return False
                    
                    # Mark as inactive
                    cur.execute("""
                        UPDATE memory.agent_snapshots 
                        SET is_active = false 
                        WHERE id = %s
                    """, (snapshot_id,))
                    
                    conn.commit()
                    
                    # Optionally remove file
                    try:
                        file_path = Path(result['file_path'])
                        if file_path.exists():
                            file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to remove snapshot file: {e}")
                    
                    logger.info(f"✅ Deleted snapshot: {snapshot_id}")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to delete snapshot: {e}")
            return False

# Global snapshot manager instance
snapshot_manager = SnapshotManager()
