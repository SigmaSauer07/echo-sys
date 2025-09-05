from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sys, os, datetime
from pathlib import Path
from memory.storage import bulk_store, get_all_memories, store_memory, import_dataset
import subprocess
import json, hashlib, tempfile, shutil, zipfile
from starlette.responses import JSONResponse
from typing import List
from lib.backup import create_backup_zip
from agents.sentinel.sentinel import trigger_sentinel

# Add parent directory to Python path so we can import modules from it.
sys.path.insert(0, str(Path(__file__).parent.parent))


# === Memory API ===
router = APIRouter(prefix="/api", tags=["Echo Memory"])
router = APIRouter()

@router.get("/api/all")
def all_memories():
    return get_all_memories()

@router.post("/api/add")
def add_memory(memory: dict):
    if "text" not in memory:
        raise HTTPException(status_code=400, detail="Memory must contain 'text'")
    
    store_memory(memory)
    trigger_sentinel(memory)
    return {"status": "ok", "memory": memory}

@router.post("/api/import")
def import_memories(file_path: str):
    imported_count = import_dataset(file_path)
    return {"status": "ok", "imported": imported_count}
# Simple in-memory store for testing
memory_store = []

class Memory(BaseModel):
    text: str
    tag: str = None
    timestamp: str = None

@router.get("/")
def ping():
    return {"message": "Echo memory API is online."}

@router.post("/add")
def add_memory(mem: Memory):
    memory_store.append(mem)
    return {"status": "success", "stored": mem}

@router.get("/all")
def get_memories():
    return memory_store

@router.post("/snapshot")
def trigger_snapshot():
    try:
        result = subprocess.run(["python3", "infra/scripts/backup/backup_to_ipfs.py"], capture_output=True, text=True)
        if result.returncode == 0:
            return {"status": "success", "message": "Snapshot saved to IPFS"}
        else:
            return {"status": "error", "stderr": result.stderr}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# === Dataset Import ===
@router.post("/import")
async def import_dataset(file: UploadFile = File(...)):
    """
    Import a dataset (NDJSON, JSON, or ZIP of these) into the memory DB.
    All memories default to agent_access=["echo"] unless specified.
    """
    try:
        tmp_dir = Path(tempfile.mkdtemp())
        file_path = tmp_dir / file.filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        extracted_files = []
        if file_path.suffix == ".zip":
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(tmp_dir)
                extracted_files = list(tmp_dir.glob("**/*"))
        else:
            extracted_files = [file_path]

        imported_count = 0
        for f in extracted_files:
            if f.suffix in [".json", ".ndjson"]:
                with open(f, "r", encoding="utf-8") as src:
                    data = [json.loads(line) for line in src]

                memories = []
                for entry in data:
                    if not entry.get("text"):
                        continue
                    mem_id = hashlib.blake2b(entry["text"].encode(), digest_size=8).hexdigest()
                    memories.append({
                        "mem_id": mem_id,
                        "text": entry["text"],
                        "source": entry.get("source", "chat_history"),
                        "metadata": {
                            **entry.get("metadata", {}),
                            "agent_access": entry.get("metadata", {}).get("agent_access", ["echo"])
                        }
                    })
                bulk_store(memories)
                imported_count += len(memories)

        return JSONResponse({"status": "success", "imported": imported_count})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.get("/api/backup")
def backup_data():
    """
    Generate and download a full backup ZIP (Postgres dump, Qdrant data, logs).
    """
    zip_path = create_backup_zip()
    if not os.path.exists(zip_path):
        return {"status": "error", "message": "Backup failed"}
    return FileResponse(zip_path, filename=os.path.basename(zip_path))
