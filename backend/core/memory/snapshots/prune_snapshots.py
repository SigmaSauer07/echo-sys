import os
import shutil

def prune_old_snapshots(snapshot_dir, max_snapshots):
    snapshots = sorted(os.listdir(snapshot_dir))
    excess = len(snapshots) - max_snapshots
    if excess > 0:
        for snap in snapshots[:excess]:
            path = os.path.join(snapshot_dir, snap)
            print(f"🗑 Removing old snapshot: {path}")
            shutil.rmtree(path, ignore_errors=True)