
# --- Imports ---
import os
import time
import logging
import importlib.util
import json
import subprocess
import random
import datetime
from fastapi import FastAPI, Request

# --- App and config ---
app = FastAPI()
AGENTS_PATH = "backend/agents"
REMOTE_SECRET = os.environ.get("REMOTE_SECRET", "changeme")
RATE_LIMIT = 10  # max requests per minute per client
_remote_rate_limit = {}
logging.basicConfig(level=logging.INFO)

# --- Free global tools ---

# --- Endpoints ---
@app.get("/tools")
async def list_tools():
    return {"tools": list(GLOBAL_TOOLS.keys())}

# Remote endpoint with access control, logging, and rate limiting
@app.post("/remote")
async def remote(request: Request):
    req = await request.json()
    secret = req.get("secret")
    client_id = req.get("client_id")
    if not client_id:
        # fallback to remote address if available
        client = getattr(request, "client", None)
        client_id = getattr(client, "host", "anonymous")
    now = int(time.time()) // 60  # current minute
    # Rate limiting
    key = f"{client_id}:{now}"
    _remote_rate_limit.setdefault(key, 0)
    if _remote_rate_limit[key] >= RATE_LIMIT:
        logging.warning(f"Rate limit exceeded for {client_id}")
        return {"error": "Rate limit exceeded"}
    _remote_rate_limit[key] += 1
    # Access control
    if secret != REMOTE_SECRET:
        logging.warning(f"Unauthorized remote access attempt from {client_id}")
        return {"error": "Unauthorized"}
    tool = req.get("tool")
    agent_name = req.get("agent")
    message = req.get("message", "")
    logging.info(f"Remote request from {client_id}: tool={tool}, agent={agent_name}, message={message}")
    if tool in GLOBAL_TOOLS:
        return {"response": GLOBAL_TOOLS[tool](message)}
    if agent_name and agent_name in agents:
        response = agents[agent_name]["module"].respond(message, agents[agent_name]["config"])
        return {"response": response}
    return {"error": "Tool or agent not found"}

app = FastAPI()
AGENTS_PATH = "backend/agents"

# Free global tools
import random, datetime
def tool_echo(message, config=None):
    return f"Echo: {message}"
def tool_math(message, config=None):
    try:
        result = eval(message, {"__builtins__": {}})
        return f"Result: {result}"
    except Exception as e:
        return f"Math error: {e}"
def tool_upper(message, config=None):
    return message.upper()
def tool_lower(message, config=None):
    return message.lower()
def tool_date(message, config=None):
    return str(datetime.datetime.now())
def tool_random(message, config=None):
    return str(random.randint(0, 1000000))

GLOBAL_TOOLS = {
    "echo": tool_echo,
    "math": tool_math,
    "upper": tool_upper,
    "lower": tool_lower,
    "date": tool_date,
    "random": tool_random,
}

# Dynamically discover and load agent modules
agents = {}

def load_agents():
    for folder in os.listdir(AGENTS_PATH):
        agent_dir = os.path.join(AGENTS_PATH, folder)
        agent_file = os.path.join(agent_dir, "agent.py")
        config_file = os.path.join(agent_dir, "config.json")
        if os.path.isfile(agent_file):
            spec = importlib.util.spec_from_file_location(folder, agent_file)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with open(config_file, 'r') as f:
                    config = json.load(f)
                agents[folder] = {
                    "module": module,
                    "config": config
                }


load_agents()


# Satellite server management
satellites = {}
core_openai_key = None

@app.post("/spawn_satellite")
async def spawn_satellite(request: Request):
    req = await request.json()
    tools = req.get("tools", [])
    api_keys = req.get("api_keys", {})
    openai_key = req.get("openai_key")
    port = req.get("port", 9000 + len(satellites))
    env = os.environ.copy()
    env["SATELLITE_TOOLS"] = ",".join(tools)
    env["SATELLITE_API_KEYS"] = json.dumps(api_keys)
    if openai_key:
        env["SATELLITE_OPENAI_KEY"] = openai_key
    cmd = [
        "uvicorn",
        "backend.satellite_template:app",
        "--host", "0.0.0.0",
        "--port", str(port),
    ]
    proc = subprocess.Popen(cmd, env=env)
    satellites[port] = {"pid": proc.pid, "tools": tools, "api_keys": api_keys, "openai_key": openai_key}
    return {"status": "launched", "port": port, "pid": proc.pid}

@app.get("/satellites")
async def list_satellites():
    return satellites

@app.get("/satellite/{port}")
async def get_satellite(port: int):
    return satellites.get(port, {"error": "Not found"})

@app.post("/satellite/{port}/stop")
async def stop_satellite(port: int):
    sat = satellites.get(port)
    if not sat:
        return {"error": "Not found"}
    try:
        os.kill(sat["pid"], 9)
        del satellites[port]
        return {"status": "stopped", "port": port}
    except Exception as e:
        return {"error": str(e)}

@app.post("/satellite/{port}/update")
async def update_satellite(port: int, request: Request):
    req = await request.json()
    sat = satellites.get(port)
    if not sat:
        return {"error": "Not found"}
    # Only allow updating tools/api_keys/openai_key
    for k in ["tools", "api_keys", "openai_key"]:
        if k in req:
            sat[k] = req[k]
    return {"status": "updated", "port": port, "config": sat}

# Core OpenAI key management
@app.post("/set_openai_key")
async def set_openai_key(request: Request):
    global core_openai_key
    req = await request.json()
    core_openai_key = req.get("openai_key")
    return {"status": "set", "openai_key": core_openai_key}

@app.get("/get_openai_key")
async def get_openai_key():
    return {"openai_key": core_openai_key}


# Unified /chat endpoint for both agents and global tools
@app.post("/chat")
async def chat(request: Request):
    req = await request.json()
    tool = req.get("tool")
    agent_name = req.get("agent")
    message = req.get("message", "")
    if tool in GLOBAL_TOOLS:
        return {"response": GLOBAL_TOOLS[tool](message)}
    if agent_name and agent_name in agents:
        response = agents[agent_name]["module"].respond(message, agents[agent_name]["config"])
        return {"response": response}
    return {"error": "Tool or agent not found"}
