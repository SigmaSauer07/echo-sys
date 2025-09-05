# memory/vector_store.py
import uuid, os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from typing import List

# backend/core/memory/vector_store.py
class VectorStore:
    def __init__(self, driver):
        self.driver = driver

    def upsert(self, vectors, payloads, ids=None):
        return self.driver.upsert(vectors, payloads, ids=ids)

    def query(self, vector, top_k=8, filter=None):
        return self.driver.query(vector, top_k=top_k, filter=filter)

    def _connect(self):
        """Attempt to connect to Qdrant"""
        try:
            self.client = QdrantClient(host=self.host, port=self.port, check_compatibility=False)
            self.client.get_collections()  # Test connection
            self.connected = True
            self.ensure_collection()
            print(f"✅ Connected to Qdrant at {self.host}:{self.port}")
        except Exception as e:
            print(f"⚠️  Failed to connect to Qdrant: {e}")
            self.connected = False
            self.client = None

    def ensure_collection(self):
        """Ensure collection exists if connected"""
        if not self.connected or not self.client:
            return

        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection not in collections:
                self.client.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE)
                )
                print(f"✅ Created collection: {self.collection}")
        except Exception as e:
            print(f"⚠️  Failed to ensure collection: {e}")
            self.connected = False

    def insert(self, text: str, embedding: List[float], namespace: str = "default") -> str:
        """Insert a vector into the store"""
        if not self.connected:
            print("⚠️  Qdrant not connected, skipping vector insert")
            return str(uuid.uuid4())  # Return dummy ID

        try:
            point_id = str(uuid.uuid4())
            payload = {"text": text, "namespace": namespace}
            point = PointStruct(id=point_id, vector=embedding, payload=payload)
            self.client.upsert(collection_name=self.collection, points=[point])
            return point_id
        except Exception as e:
            print(f"⚠️  Failed to insert vector: {e}")
            return str(uuid.uuid4())  # Return dummy ID

    def search(self, embedding: List[float], top_k: int = 5, namespace: str = "default") -> List[dict]:
        """Search for similar vectors"""
        if not self.connected:
            print("⚠️  Qdrant not connected, returning empty results")
            return []

        try:
            filt = Filter(must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))])
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=embedding,
                limit=top_k,
                query_filter=filt
            )
            return [{"id": hit.id, "score": hit.score, "text": hit.payload["text"]} for hit in hits]
        except Exception as e:
            print(f"⚠️  Failed to search vectors: {e}")
            return []

    def delete_namespace(self, namespace: str):
        """Delete all vectors in a namespace"""
        if not self.connected:
            print("⚠️  Qdrant not connected, skipping delete")
            return

        try:
            self.client.delete(
                collection_name=self.collection,
                filter=Filter(must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))])
            )
        except Exception as e:
            print(f"⚠️  Failed to delete namespace: {e}")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = "memory_vectors"

client = QdrantClient(url=QDRANT_URL)

def init_vector_store():
    if not client.collection_exists(COLLECTION_NAME):
        client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
        )

def add_vector(id_: int, vector: List[float]):
    init_vector_store()
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[models.PointStruct(id=id_, vector=vector, payload={})]
    )

def search_vectors(vector: List[float], limit=5):
    init_vector_store()
    return client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=limit
    )
