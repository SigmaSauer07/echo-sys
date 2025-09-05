"""
Data Persistence & Reliability Module for AlsaniaMCP
Ensures data integrity and persistence across database restarts
"""

import asyncio
import hashlib
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from config.config import config

logger = logging.getLogger("alsaniamcp.persistence")

class PersistenceManager:
    """Manages data persistence and integrity across Qdrant and PostgreSQL"""
    
    def __init__(self):
        self.postgres_url = config.POSTGRES_URL
        self.qdrant_client = None
        self.last_integrity_check = None
        
    def get_postgres_connection(self):
        """Get PostgreSQL connection with proper error handling"""
        try:
            return psycopg2.connect(
                self.postgres_url,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def get_qdrant_client(self):
        """Get Qdrant client with proper error handling"""
        if not self.qdrant_client:
            try:
                qdrant_url = config.QDRANT_URL
                if qdrant_url.startswith('http://'):
                    host = qdrant_url.replace('http://', '').split(':')[0]
                    port = int(qdrant_url.split(':')[-1]) if ':' in qdrant_url.split('//')[1] else 6333
                else:
                    host = 'localhost'
                    port = 6333
                
                self.qdrant_client = QdrantClient(host=host, port=port, check_compatibility=False)
                # Test connection
                self.qdrant_client.get_collections()
                logger.info(f"✅ Connected to Qdrant at {host}:{port}")
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                raise
        return self.qdrant_client
    
    async def verify_data_integrity(self) -> Dict[str, any]:
        """Comprehensive data integrity verification"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "postgres": {"status": "unknown", "details": {}},
            "qdrant": {"status": "unknown", "details": {}},
            "consistency": {"status": "unknown", "details": {}},
            "overall_status": "unknown"
        }
        
        try:
            # Verify PostgreSQL integrity
            postgres_results = await self._verify_postgres_integrity()
            results["postgres"] = postgres_results
            
            # Verify Qdrant integrity
            qdrant_results = await self._verify_qdrant_integrity()
            results["qdrant"] = qdrant_results
            
            # Verify cross-database consistency
            consistency_results = await self._verify_cross_db_consistency()
            results["consistency"] = consistency_results
            
            # Determine overall status
            if (postgres_results["status"] == "healthy" and 
                qdrant_results["status"] == "healthy" and 
                consistency_results["status"] == "consistent"):
                results["overall_status"] = "healthy"
            elif (postgres_results["status"] == "degraded" or 
                  qdrant_results["status"] == "degraded"):
                results["overall_status"] = "degraded"
            else:
                results["overall_status"] = "critical"
                
            self.last_integrity_check = datetime.now()
            logger.info(f"Data integrity check completed: {results['overall_status']}")
            
        except Exception as e:
            logger.error(f"Data integrity verification failed: {e}")
            results["overall_status"] = "error"
            results["error"] = str(e)
        
        return results
    
    async def _verify_postgres_integrity(self) -> Dict[str, any]:
        """Verify PostgreSQL data integrity"""
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Check table existence and structure
                    cur.execute("""
                        SELECT table_name, column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_schema IN ('memory', 'forensics', 'agents')
                        ORDER BY table_name, ordinal_position
                    """)
                    schema_info = cur.fetchall()
                    
                    # Count records in each table
                    tables_info = {}
                    for table in ['memory.memories', 'forensics.access_logs', 'agents.agent_states', 'memory.snapshots']:
                        try:
                            cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                            count = cur.fetchone()['count']
                            
                            cur.execute(f"SELECT MAX(created_at) as latest FROM {table}")
                            latest = cur.fetchone()['latest']
                            
                            tables_info[table] = {
                                "record_count": count,
                                "latest_record": latest.isoformat() if latest else None
                            }
                        except Exception as e:
                            tables_info[table] = {"error": str(e)}
                    
                    # Check for orphaned records
                    cur.execute("""
                        SELECT COUNT(*) as orphaned_logs
                        FROM forensics.access_logs al
                        LEFT JOIN memory.memories m ON al.memory_id = m.id
                        WHERE m.id IS NULL AND al.memory_id IS NOT NULL
                    """)
                    orphaned_logs = cur.fetchone()['orphaned_logs']
                    
                    return {
                        "status": "healthy",
                        "details": {
                            "schema_tables": len(set(row['table_name'] for row in schema_info)),
                            "tables_info": tables_info,
                            "orphaned_logs": orphaned_logs,
                            "connection_pool": "active"
                        }
                    }
                    
        except Exception as e:
            logger.error(f"PostgreSQL integrity check failed: {e}")
            return {
                "status": "critical",
                "details": {"error": str(e)}
            }
    
    async def _verify_qdrant_integrity(self) -> Dict[str, any]:
        """Verify Qdrant data integrity"""
        try:
            client = self.get_qdrant_client()
            
            # Get collection info
            collections = client.get_collections()
            collection_details = {}
            
            for collection in collections.collections:
                collection_name = collection.name
                try:
                    info = client.get_collection(collection_name)
                    collection_details[collection_name] = {
                        "vectors_count": info.vectors_count,
                        "indexed_vectors_count": info.indexed_vectors_count,
                        "points_count": info.points_count,
                        "status": info.status.value if hasattr(info.status, 'value') else str(info.status)
                    }
                except Exception as e:
                    collection_details[collection_name] = {"error": str(e)}
            
            return {
                "status": "healthy",
                "details": {
                    "collections_count": len(collections.collections),
                    "collections": collection_details,
                    "connection": "active"
                }
            }
            
        except Exception as e:
            logger.error(f"Qdrant integrity check failed: {e}")
            return {
                "status": "critical",
                "details": {"error": str(e)}
            }
    
    async def _verify_cross_db_consistency(self) -> Dict[str, any]:
        """Verify consistency between PostgreSQL and Qdrant"""
        try:
            # Get memory count from PostgreSQL
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as pg_count FROM memory.memories")
                    pg_count = cur.fetchone()['pg_count']
            
            # Get points count from Qdrant (if collection exists)
            client = self.get_qdrant_client()
            qdrant_count = 0
            
            try:
                collections = client.get_collections()
                for collection in collections.collections:
                    if collection.name == "alsania_mem":
                        info = client.get_collection("alsania_mem")
                        qdrant_count = info.points_count
                        break
            except Exception as e:
                logger.warning(f"Could not get Qdrant collection info: {e}")
            
            # Calculate consistency ratio
            if pg_count == 0 and qdrant_count == 0:
                consistency_ratio = 1.0
                status = "consistent"
            elif pg_count == 0 or qdrant_count == 0:
                consistency_ratio = 0.0
                status = "inconsistent"
            else:
                consistency_ratio = min(pg_count, qdrant_count) / max(pg_count, qdrant_count)
                status = "consistent" if consistency_ratio >= 0.95 else "inconsistent"
            
            return {
                "status": status,
                "details": {
                    "postgres_records": pg_count,
                    "qdrant_points": qdrant_count,
                    "consistency_ratio": round(consistency_ratio, 3),
                    "threshold": 0.95
                }
            }
            
        except Exception as e:
            logger.error(f"Cross-database consistency check failed: {e}")
            return {
                "status": "error",
                "details": {"error": str(e)}
            }
    
    async def create_data_backup(self, backup_name: Optional[str] = None) -> Dict[str, any]:
        """Create a comprehensive backup of all data"""
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_results = {
            "backup_name": backup_name,
            "timestamp": datetime.now().isoformat(),
            "postgres_backup": None,
            "qdrant_backup": None,
            "status": "unknown"
        }
        
        try:
            # Create PostgreSQL backup
            pg_backup = await self._backup_postgres_data(backup_name)
            backup_results["postgres_backup"] = pg_backup
            
            # Create Qdrant backup
            qdrant_backup = await self._backup_qdrant_data(backup_name)
            backup_results["qdrant_backup"] = qdrant_backup
            
            backup_results["status"] = "completed"
            logger.info(f"Data backup completed: {backup_name}")
            
        except Exception as e:
            logger.error(f"Data backup failed: {e}")
            backup_results["status"] = "failed"
            backup_results["error"] = str(e)
        
        return backup_results
    
    async def _backup_postgres_data(self, backup_name: str) -> Dict[str, any]:
        """Backup PostgreSQL data"""
        backup_dir = Path("backups") / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with self.get_postgres_connection() as conn:
                with conn.cursor() as cur:
                    # Backup each table
                    tables = ['memory.memories', 'forensics.access_logs', 'agents.agent_states', 'memory.snapshots']
                    table_backups = {}
                    
                    for table in tables:
                        cur.execute(f"SELECT * FROM {table}")
                        rows = cur.fetchall()
                        
                        # Convert to JSON-serializable format
                        serializable_rows = []
                        for row in rows:
                            row_dict = dict(row)
                            # Convert datetime objects to ISO strings
                            for key, value in row_dict.items():
                                if isinstance(value, datetime):
                                    row_dict[key] = value.isoformat()
                            serializable_rows.append(row_dict)
                        
                        # Save to file
                        table_file = backup_dir / f"{table.replace('.', '_')}.json"
                        with open(table_file, 'w') as f:
                            json.dump(serializable_rows, f, indent=2)
                        
                        table_backups[table] = {
                            "records": len(serializable_rows),
                            "file": str(table_file)
                        }
            
            return {
                "status": "completed",
                "tables": table_backups,
                "backup_dir": str(backup_dir)
            }
            
        except Exception as e:
            logger.error(f"PostgreSQL backup failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def _backup_qdrant_data(self, backup_name: str) -> Dict[str, any]:
        """Backup Qdrant data"""
        backup_dir = Path("backups") / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            client = self.get_qdrant_client()
            collections = client.get_collections()
            
            collection_backups = {}
            for collection in collections.collections:
                collection_name = collection.name
                
                # Get all points from collection
                points = client.scroll(
                    collection_name=collection_name,
                    limit=10000,  # Adjust based on expected data size
                    with_payload=True,
                    with_vectors=True
                )
                
                # Save collection data
                collection_file = backup_dir / f"qdrant_{collection_name}.json"
                collection_data = {
                    "collection_name": collection_name,
                    "points": [
                        {
                            "id": point.id,
                            "vector": point.vector,
                            "payload": point.payload
                        }
                        for point in points[0]  # points is a tuple (points, next_page_offset)
                    ]
                }
                
                with open(collection_file, 'w') as f:
                    json.dump(collection_data, f, indent=2)
                
                collection_backups[collection_name] = {
                    "points": len(collection_data["points"]),
                    "file": str(collection_file)
                }
            
            return {
                "status": "completed",
                "collections": collection_backups,
                "backup_dir": str(backup_dir)
            }
            
        except Exception as e:
            logger.error(f"Qdrant backup failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

# Global persistence manager instance
persistence_manager = PersistenceManager()
