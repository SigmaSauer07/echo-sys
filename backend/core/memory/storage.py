# memory/storage.py
import os, json, uuid, psycopg2
import psycopg2.extras as RealDictCursor
from qdrant_client import QdrantClient
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from infra.scripts.embedding.embedding import get_embedding as embed_text

SNAPSHOT_DIR = "snapshots"
qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"), api_key=os.getenv("QDRANT_API_KEY"))
DB_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:mem0pass@postgres:5432/mem0")

def get_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def init_storage():
    """Initialize table if not exists"""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY,
            text TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW()
        )
        """)
        conn.commit()

def store_memory(memory: dict):
    """Save memory to Postgres"""
    init_storage()
    text = memory.get("text", "")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO memories (text) VALUES (%s)", (text,))
        conn.commit()

def get_all_memories():
    """Retrieve all memories from Postgres"""
    init_storage()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, text, timestamp FROM memories ORDER BY timestamp DESC")
        return cur.fetchall()

def import_dataset(file_path: str):
    """Bulk import dataset from NDJSON"""
    import json
    count = 0
    init_storage()
    with open(file_path, "r") as f, get_connection() as conn, conn.cursor() as cur:
        for line in f:
            data = json.loads(line)
            text = data.get("text", "")
            cur.execute("INSERT INTO memories (text) VALUES (%s)", (text,))
            count += 1
        conn.commit()
    return count

def bulk_store(memories):
    """Store memories directly in Postgres and Qdrant."""
    conn = psycopg2.connect(os.getenv("POSTGRES_URL", "postgresql://postgres:mem0pass@postgres:5432/mem0"))
    cur = conn.cursor()

    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            mem_id TEXT PRIMARY KEY,
            text TEXT,
            source TEXT,
            metadata JSONB
        )
    """)

    for mem in memories:
        cur.execute(
            """
            INSERT INTO memories (mem_id, text, source, metadata)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (mem_id) DO NOTHING
            """,
            (mem["mem_id"], mem["text"], mem["source"], json.dumps(mem["metadata"]))
        )

        # Insert into Qdrant (dummy embedding for now)
        qdrant.upsert(
            collection_name="alsaniamcp",
            points=[{
                "id": mem["mem_id"],
                "vector": embed_text(mem["text"]),
                "payload": mem
            }]
        )

    conn.commit()
    cur.close()
    conn.close()

def embed_text(text: str):
    return [float(ord(c) % 10) for c in text[:64]]  # Dummy embedding

def ensure_dir():
    if not os.path.exists(SNAPSHOT_DIR):
        os.makedirs(SNAPSHOT_DIR)

def save_snapshot(data: dict, name: str = None) -> str:
    ensure_dir()
    snapshot_id = name or str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
    with open(path, "w") as f:
        json.dump({"id": snapshot_id, "timestamp": timestamp, "data": data}, f, indent=2)
    return snapshot_id

def load_snapshot(snapshot_id: str) -> dict:
    path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Snapshot {snapshot_id} not found.")
    with open(path, "r") as f:
        return json.load(f)

def list_snapshots() -> list:
    ensure_dir()
    return [f[:-5] for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")]

def delete_snapshot(snapshot_id: str):
    path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
    if os.path.exists(path):
        os.remove(path)
