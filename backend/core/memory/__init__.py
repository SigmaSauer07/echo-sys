import os
from .vector_store import VectorStore

def get_vector_store(embedding_dim: int):
    backend = os.getenv("MCP_VECTOR_BACKEND", "qdrant").lower()
    if backend == "qdrant":
        from .adapters.qdrant.driver import QdrantVectorDriver
        drv = QdrantVectorDriver()
        drv.ensure_collection(embedding_dim)
        return VectorStore(drv)
    elif backend == "mem0":
        from .adapters.mem0.driver import Mem0Driver
        return VectorStore(Mem0Driver())
    else:
        raise ValueError(f"Unsupported MCP_VECTOR_BACKEND: {backend}")
