from __future__ import annotations
import os
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

class QdrantVectorDriver:
    def __init__(self, collection: Optional[str] = None):
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        api_key = os.getenv("QDRANT_API_KEY")
        self.collection = collection or os.getenv("QDRANT_COLLECTION", "alsania_mem")
        self.client = QdrantClient(url=url, api_key=api_key)

    def ensure_collection(self, vector_size: int):
        if self.collection not in [c.name for c in self.client.get_collections().collections]:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: Optional[List[int]]=None):
        points = [
            PointStruct(id=ids[i] if ids else None, vector=vectors[i], payload=payloads[i])
            for i in range(len(vectors))
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def query(self, vector: List[float], top_k: int = 8, filter: Optional[Dict[str, Any]] = None):
        res = self.client.search(collection_name=self.collection, query_vector=vector, limit=top_k, query_filter=filter)
        return [{"id":r.id, "score":r.score, "payload":r.payload} for r in res]
