import subprocess
import time
import requests
import os
import json

IPFS_API = "http://127.0.0.1:5001/api/v0"
REGISTRY_FILE = "/app/backups/agent_registry.json"
REGISTRY_KEY = "alsania-agents-latest"

def start_ipfs():
    proc = subprocess.Popen(["ipfs", "daemon"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(30):
        try:
            requests.post(f"{IPFS_API}/id", timeout=2)
            return proc
        except Exception:
            time.sleep(1)
    raise RuntimeError("IPFS daemon did not become ready")

def stop_ipfs(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

def add_to_ipfs(file_path: str) -> str:
    """Add a file to IPFS and return its CID."""
    proc = start_ipfs()
    try:
        with open(file_path, "rb") as f:
            res = requests.post(f"{IPFS_API}/add", files={"file": f}).json()
        return res["Hash"]
    finally:
        stop_ipfs(proc)

def ensure_key(key_name: str):
    keys = requests.post(f"{IPFS_API}/key/list").json()
    if not any(k["Name"] == key_name for k in keys["Keys"]):
        requests.post(f"{IPFS_API}/key/gen?arg={key_name}&type=rsa&size=2048")

def publish_to_ipns(cid: str, key_name: str) -> str:
    """Publish a CID to IPNS under a specific agent key."""
    ensure_key(key_name)
    res = requests.post(f"{IPFS_API}/name/publish?arg=/ipfs/{cid}&key={key_name}").json()
    return res["Name"]  # IPNS name

def link_ipld(agent: str, new_cid: str) -> str:
    """Link snapshot CID into the agent’s IPLD chain, return new IPLD head CID."""
    prev_cid = None
    latest_file = f"/app/backups/{agent}_latest.txt"
    if os.path.exists(latest_file):
        with open(latest_file, "r") as f:
            prev_cid = f.read().strip()

    node = {"agent": agent, "current": new_cid}
    if prev_cid:
        node["previous"] = prev_cid

    with open("ipld_node.json", "w") as f:
        json.dump(node, f)

    with open("ipld_node.json", "rb") as f:
        res = requests.post(f"{IPFS_API}/add", files={"file": f}).json()

    ipld_cid = res["Hash"]
    with open(latest_file, "w") as f:
        f.write(ipld_cid)

    return ipld_cid

def update_registry(agent: str, ipns_name: str) -> str:
    """Update global registry of agents → IPNS pointers and republish."""
    registry = {}
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r") as f:
            registry = json.load(f)

    registry[agent] = ipns_name

    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)

    # Add to IPFS and republish
    with open(REGISTRY_FILE, "rb") as f:
        res = requests.post(f"{IPFS_API}/add", files={"file": f}).json()
    cid = res["Hash"]

    ensure_key(REGISTRY_KEY)
    res = requests.post(f"{IPFS_API}/name/publish?arg=/ipfs/{cid}&key={REGISTRY_KEY}").json()
    return res["Name"]  # Global registry IPNS
