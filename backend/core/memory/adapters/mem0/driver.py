import os, json, pathlib
from typing import List, Dict, Any, Optional

class Mem0Driver:
    """
    Minimal in-process vector stub (use when you want everything local + simple).
    Not a true ANN index; keeps it dead-simple for low-end devices.
    """
    def __init__(self, data_dir: Optional[str] = None):
        self.data_path = pathlib.Path(data_dir or os.getenv("MEM0_DATA_DIR", "./data/mem0"))
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.store_file = self.data_path / "mem.jsonl"
        if not self.store_file.exists():
            self.store_file.write_text("", encoding="utf-8")

    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids=None):
        with self.store_file.open("a", encoding="utf-8") as f:
            for vec, pl in zip(vectors, payloads):
                f.write(json.dumps({"v": vec, "p": pl}) + "\n")

    def query(self, vector: List[float], top_k: int = 8, filter=None):
        # cosine similarity in pure python — fine for small/local
        import math, json
        items = []
        with self.store_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                v = obj["v"]
                dot = sum(a*b for a,b in zip(v, vector))
                nv = math.sqrt(sum(a*a for a in v)) or 1e-9
                nq = math.sqrt(sum(a*a for a in vector)) or 1e-9
                score = dot/(nv*nq)
                items.append((score, obj["p"]))
        items.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, "payload": p} for s,p in items[:top_k]]
