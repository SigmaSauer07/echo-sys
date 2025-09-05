from fastapi import APIRouter
import psutil
import os
import json
from datetime import datetime
import logging

logger = logging.getLogger("alsaniamcp.metrics")
router = APIRouter(prefix="/metrics", tags=["System Metrics"])

@router.get("/health")
def health_check():
    """Basic health check for metrics service."""
    return {
        "status": "running",
        "pid": os.getpid(),
        "timestamp": datetime.now().isoformat()
    }

@router.get("/cpu")
def cpu_usage():
    """Get CPU usage metrics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        return {
            "cpu_percent": round(cpu_percent, 1),
            "cpu_count": cpu_count,
            "cpu_freq_current": round(cpu_freq.current, 1) if cpu_freq else None,
            "cpu_freq_max": round(cpu_freq.max, 1) if cpu_freq else None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get CPU metrics: {e}")
        return {"error": "Failed to get CPU metrics", "cpu_percent": 0}

@router.get("/memory")
def memory_usage():
    """Get memory usage metrics."""
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": round(mem.percent, 1),
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": round(swap.percent, 1),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get memory metrics: {e}")
        return {"error": "Failed to get memory metrics", "percent": 0}

@router.get("/disk")
def disk_usage():
    """Get disk usage metrics."""
    try:
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()

        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round(disk.percent, 1),
            "read_bytes": disk_io.read_bytes if disk_io else 0,
            "write_bytes": disk_io.write_bytes if disk_io else 0,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get disk metrics: {e}")
        return {"error": "Failed to get disk metrics", "percent": 0}

@router.get("/quarantine_log")
def quarantine_log():
    try:
        with open("logs/forensics.log", "r") as f:
            lines = f.readlines()[-20:]
            return {"entries": [json.loads(line) for line in lines if '"quarantine"' in line]}
    except Exception as e:
        return {"error": str(e)}