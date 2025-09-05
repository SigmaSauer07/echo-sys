import asyncio, requests, os, json
import base64, threading
import logging
import schedule, time
import subprocess
from memory.storage import store_memory
from lib.logger import log_event


logger = logging.getLogger("alsaniamcp.sentinel")
logging.basicConfig(level=logging.INFO)
MCP_URL = os.getenv("MCP_URL", "http://localhost:8050")

def is_obfuscated(text):
    try:
        return base64.b64encode(base64.b64decode(text)).decode() == text
    except Exception:
        return False

async def check_memory_integrity():
    """Check memory integrity and quarantine suspicious entries"""
    while True:
        try:
            # Note: This endpoint doesn't exist yet, so we'll skip the actual checks for now
            # but keep the structure for when the endpoint is implemented
            logger.info("🛡️ Running memory integrity check...")

            # TODO: Implement actual memory scanning when /memories endpoint exists
            # res = requests.get(f"{MCP_URL}/memories?limit=10").json()
            # for memory in res.get("data", []):
            #     text = memory.get("text", "")
            #     entropy = memory.get("entropy", 0)
            #     links = memory.get("links", [])
            #     ttl = memory.get("ttl", "0d")
            #
            #     if entropy > 7.5 and not links:
            #         requests.post(f"{MCP_URL}/delete", json={"id": memory["id"]})
            #         logger.warning(f"Deleted high-entropy memory: {memory['id']}")
            #
            #     if "d" in ttl and int(ttl.replace("d", "")) > 30 and is_obfuscated(text):
            #         requests.post(f"{MCP_URL}/quarantine", json={"id": memory["id"]})
            #         logger.warning(f"Quarantined suspicious memory: {memory['id']}")

            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"❌ Sentinel check failed: {e}")
            await asyncio.sleep(300)  # Retry in 5 minutes on failure

def run_backup():
    subprocess.run(["python3", "infra/scripts/backup/backup_to_ipfs.py"])

def start_scheduler():
    schedule.every().day.at("03:33").do(run_backup)
    while True:
        schedule.run_pending()
        time.sleep(30)

def start():
    t = threading.Thread(target=start_scheduler, daemon=True)
    t.start()

def start_sentinel():
    """Start sentinel monitoring in background"""
    logger.info("🛡️ Starting Sentinel")
    # Create background task for memory integrity checks
    asyncio.create_task(check_memory_integrity())

    # Start scheduler to run backups daily at 3:33 AM
    start()
def timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def trigger_sentinel(memory):
    log_event(f"[Sentinel] Triggered at {timestamp}: {memory.get('text', '')}")
    print("[Sentinel] Triggered:", memory.get("text"))
    store_memory(memory)

if __name__ == "__main__":
    asyncio.run(check_memory_integrity())
