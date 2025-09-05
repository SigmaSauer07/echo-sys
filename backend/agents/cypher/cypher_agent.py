def respond(message, config=None):
    """Simple respond interface for Cypher agent."""
    # Optionally, parse message for commands or trigger task logic
    if message.strip().lower() == "status":
        return "Cypher agent is online."
    elif message.strip().lower().startswith("run:"):
        cmd = message.split("run:", 1)[1].strip()
        execute_command(cmd)
        return f"Cypher executed command: {cmd}"
    else:
        return f"Cypher received: {message}"
import asyncio, os, json, requests, subprocess

CONFIG = json.load(open(os.path.join(os.path.dirname(__file__), "config.json")))
MCP_URL = "http://localhost:8050"
NAMESPACE = CONFIG.get("memory_namespace", "cypher_core")

async def process_tasks():
    print("[CYPHER] Ready to execute tasks...")
    while True:
        try:
            # Query MCP for tasks tagged 'cypher:task'
            resp = requests.get(f"{MCP_URL}/memories?namespace={NAMESPACE}&tag=cypher:task&limit=5").json()
            tasks = resp.get("data", [])

            if tasks:
                for task in tasks:
                    task_text = task.get("text", "")
                    print(f"[CYPHER] Executing task: {task_text}")
                    
                    # Example: handle known types of tasks
                    if task_text.startswith("run:"):
                        cmd = task_text.split("run:")[1].strip()
                        execute_command(cmd)
                    elif task_text.startswith("script:"):
                        script_path = task_text.split("script:")[1].strip()
                        execute_script(script_path)
                    
                    # Mark task as completed
                    complete_task(task["id"])
            else:
                print("[CYPHER] No tasks found.")

        except Exception as e:
            print(f"[CYPHER] Error: {e}")

        await asyncio.sleep(60)

def execute_command(cmd: str):
    print(f"[CYPHER] Running command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"[CYPHER] Output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"[CYPHER] Command failed: {e.stderr}")

def execute_script(script_path: str):
    print(f"[CYPHER] Running script: {script_path}")
    if os.path.exists(script_path):
        execute_command(f"python3 {script_path}")
    else:
        print(f"[CYPHER] Script not found: {script_path}")

def complete_task(task_id: str):
    try:
        requests.post(f"{MCP_URL}/memories/{task_id}/complete")
        print(f"[CYPHER] Task {task_id} marked as complete.")
    except:
        print("[CYPHER] Failed to mark task complete.")

async def start():
    await process_tasks()
