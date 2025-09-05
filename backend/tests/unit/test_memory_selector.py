import os
from backend.core.memory import get_vector_store

def test_qdrant_selected(monkeypatch):
    monkeypatch.setenv("MCP_VECTOR_BACKEND", "qdrant")
    vs = get_vector_store(128)
    assert vs.driver.__class__.__name__ == "QdrantVectorDriver"

def test_mem0_selected(monkeypatch):
    monkeypatch.setenv("MCP_VECTOR_BACKEND", "mem0")
    vs = get_vector_store(128)
    assert vs.driver.__class__.__name__ == "Mem0Driver"
