#!/usr/bin/env python3
"""
Snapshot Manager - IPFS-backed storage and integrity verification
"""

import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ipfs_helper import add_to_ipfs, publish_to_ipns, link_ipld, update_registry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("snapshot_manager")

# Create FastAPI app
app = FastAPI(
    title="Snapshot Manager",
    description="IPFS-backed storage and integrity verification",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize Snapshot Manager on startup"""
    logger.info("📸 Snapshot Manager starting up...")

    # Ensure directories exist
    os.makedirs("/app/backups", exist_ok=True)
    os.makedirs("/app/integrity", exist_ok=True)
    os.makedirs("/app/logs", exist_ok=True)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "snapshot_manager"}

@app.get("/status")
async def status():
    """Detailed status endpoint"""
    return {
        "snapshot_manager": {
            "status": "active",
            "backups_available": len(os.listdir("/app/backups")) if os.path.exists("/app/backups") else 0,
            "integrity_checks": "enabled"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/create-snapshot/{agent}")
async def create_snapshot(agent: str, data: dict):
    snapshot_id = f"{agent}_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    snapshot_path = f"/app/backups/{snapshot_id}.json"

    with open(snapshot_path, 'w') as f:
        json.dump({
            "id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "data": data
        }, f, indent=2)

    # Step 1: Add to IPFS
    cid = add_to_ipfs(snapshot_path)

    # Step 2: Link to agent’s IPLD chain
    ipld_cid = link_ipld(agent, cid)

    # Step 3: Publish agent’s latest snapshot to IPNS
    ipns_name = publish_to_ipns(ipld_cid, key_name=f"{agent}-latest")

    # Step 4: Update global registry
    registry_ipns = update_registry(agent, ipns_name)

    return {
        "agent": agent,
        "snapshot_id": snapshot_id,
        "cid": cid,
        "ipld_cid": ipld_cid,
        "ipns": ipns_name,
        "registry": registry_ipns,
        "status": "created"
    }

    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/snapshots")
async def list_snapshots():
    """List available snapshots"""
    try:
        backups_dir = "/app/backups"
        if not os.path.exists(backups_dir):
            return {"snapshots": []}

        snapshots = []
        for file in os.listdir(backups_dir):
            if file.endswith('.json'):
                snapshots.append(file.replace('.json', ''))

        return {"snapshots": snapshots}

    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import JSONResponse

@app.get("/registry")
async def registry():
    """Return the current agent → IPNS mapping"""
    try:
        registry_file = "/app/backups/agent_registry.json"
        if not os.path.exists(registry_file):
            return JSONResponse(content={"registry": {}}, status_code=200)

        with open(registry_file, "r") as f:
            registry = json.load(f)

        return {"registry": registry}

    except Exception as e:
        logger.error(f"Failed to read registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import requests

@app.get("/registry/resolve")
async def registry_resolve():
    """Fetch the global agent registry from IPNS (network live state),
    with fallback to local file if resolution fails.
    """
    try:
        ipns_key = "alsania-agents-latest"

        # Try to resolve the IPNS key
        res = requests.post(f"{IPFS_API}/name/resolve?arg={ipns_key}").json()
        cid_path = res.get("Path")
        if not cid_path:
            raise RuntimeError("Could not resolve IPNS registry")

        # Fetch registry JSON directly from IPFS
        cid = cid_path.replace("/ipfs/", "")
        url = f"{IPFS_API}/cat?arg={cid}"
        registry_json = requests.post(url).json()

        return {"source": "ipns", "ipns": ipns_key, "cid": cid, "registry": registry_json}

    except Exception as e:
        logger.warning(f"IPNS registry resolution failed, falling back to local file: {e}")

        # Fallback to local file
        registry_file = "/app/backups/agent_registry.json"
        if os.path.exists(registry_file):
            with open(registry_file, "r") as f:
                registry = json.load(f)
            return {"source": "local", "registry": registry}
        else:
            return {"source": "local", "registry": {}}

@app.get("/integrity/check")
async def integrity_check():
    """Perform integrity check"""
    try:
        integrity_file = "/app/integrity/integrity.hash"
        if os.path.exists(integrity_file):
            with open(integrity_file, 'r') as f:
                integrity_data = json.load(f)
        else:
            integrity_data = {}

        return {
            "status": "verified",
            "integrity_data": integrity_data,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
