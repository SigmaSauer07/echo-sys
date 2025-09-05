import json
import os
from datetime import datetime

FORENSICS_LOG = "logs/forensics.log"

def log_event(event_type, memory_id, details=None):
    os.makedirs("logs", exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "memory_id": memory_id,
        "details": details or {}
    }
    with open(FORENSICS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def log_access(memory_id, user="unknown"):
    log_event("access", memory_id, {"user": user})

def log_edit(memory_id, changes):
    log_event("edit", memory_id, {"changes": changes})

def log_delete_attempt(memory_id, success):
    log_event("delete_attempt", memory_id, {"success": success})

def log_quarantine(memory_id, reason):
    log_event("quarantine", memory_id, {"reason": reason})
