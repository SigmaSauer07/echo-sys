#!/usr/bin/env python3

import hashlib
import json
from pathlib import Path

SNAPSHOT_DIR = Path("snapshots")
LOG_PATH = SNAPSHOT_DIR / "log.json"
HASH_FILE = SNAPSHOT_DIR / "integrity.hash"

def compute_hash(file_path):
    h = hashlib.blake2b()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def verify_hashes():
    if not HASH_FILE.exists():
        print("❌ No hash file found. Integrity check skipped.")
        return False

    with open(HASH_FILE, "r") as f:
        saved_hashes = json.load(f)

    all_good = True
    for file, saved_hash in saved_hashes.items():
        file_path = SNAPSHOT_DIR / file
        if not file_path.exists():
            print(f"⚠️ Missing file: {file}")
            all_good = False
            continue
        current_hash = compute_hash(file_path)
        if current_hash != saved_hash:
            print(f"❌ Hash mismatch for {file}")
            print(f"  Expected: {saved_hash}")
            print(f"  Found:    {current_hash}")
            all_good = False
        else:
            print(f"✅ {file} passed integrity check.")
    return all_good

def generate_hashes():
    hashes = {}
    for file_path in SNAPSHOT_DIR.glob("*"):
        if file_path.name in {"integrity.hash", "log.json"}:
            continue
        hashes[file_path.name] = compute_hash(file_path)
    with open(HASH_FILE, "w") as f:
        json.dump(hashes, f, indent=2)
    print("✅ Integrity hashes generated and saved.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        passed = verify_hashes()
        if not passed:
            print("❌ Integrity check failed.")
            exit(1)
    else:
        generate_hashes()
