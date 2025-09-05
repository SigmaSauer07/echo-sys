import json
import os
import subprocess

SNAPSHOT_LOG = "snapshots/log.json"
DOWNLOAD_DIR = "snapshots/downloads"
RESTORE_DIR = "snapshots/restore"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(RESTORE_DIR, exist_ok=True)

def list_snapshots():
    if not os.path.exists(SNAPSHOT_LOG):
        print("No snapshot log found.")
        return []

    with open(SNAPSHOT_LOG, "r") as f:
        return json.load(f)

def prompt_user_to_select(snapshots):
    print("\nAvailable Snapshots:")
    for idx, snap in enumerate(snapshots):
        print(f"{idx+1}. {snap['file']}  (CID: {snap['cid']})")

    choice = input("\nEnter number to restore, or press Enter to skip: ")
    if choice.strip().isdigit():
        index = int(choice.strip()) - 1
        if 0 <= index < len(snapshots):
            return snapshots[index]
    return None

def download_and_restore(snapshot):
    cid = snapshot["cid"]
    file = snapshot["file"]
    url = f"https://ipfs.io/ipfs/{cid}"
    filepath = os.path.join(DOWNLOAD_DIR, file)

    print(f"\nDownloading {file} from IPFS ({cid})...")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download snapshot: {response.status_code}")

    with open(filepath, "wb") as f:
        f.write(response.content)

    print("Download complete.")

    if file.endswith(".sql"):
        subprocess.run(["psql", "-U", "postgres", "-d", "mem0", "-f", filepath])
    elif file.endswith(".tar.gz"):
        subprocess.run(["tar", "-xzvf", filepath, "-C", RESTORE_DIR])
        print("Qdrant vector data extracted. Restart Qdrant container if needed.")

if __name__ == "__main__":
    import requests

    snapshots = list_snapshots()
    if not snapshots:
        print("No snapshots to restore.")
        exit()

    selected = prompt_user_to_select(snapshots)
    if selected:
        download_and_restore(selected)
    else:
        print("Skipping snapshot restore.")