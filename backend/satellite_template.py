# Satellite template for non-API-key clients (e.g., VS Code extensions)
import os
import json
from fastapi import FastAPI, Request

app = FastAPI()

# Remote endpoint for non-API-key clients (e.g., VS Code extensions)
@app.post("/remote")
async def remote(request: Request):
    req = await request.json()
    tool = req.get("tool")
    message = req.get("message", "")
    # No API key required, but you can add checks here if needed
    api_key = API_KEYS.get(tool)
    func = TOOL_FUNCS.get(tool)
    if not func:
        return {"error": "Tool not implemented."}
    return {"response": func(message, api_key)}


TOOLS = os.environ.get("SATELLITE_TOOLS", "").split(",") if os.environ.get("SATELLITE_TOOLS") else []
API_KEYS = json.loads(os.environ.get("SATELLITE_API_KEYS", "{}"))
OPENAI_KEY = os.environ.get("SATELLITE_OPENAI_KEY")


# Tool logic
def tool_echo(message, api_key=None):
    return f"Echo: {message}"

def tool_math(message, api_key=None):
    try:
        result = eval(message, {"__builtins__": {}})
        return f"Result: {result}"
    except Exception as e:
        return f"Math error: {e}"

def tool_openai(message, api_key=None):
    # Placeholder for OpenAI logic
    return f"[OpenAI] Would call OpenAI API with key: {api_key or OPENAI_KEY} and message: {message}"

TOOL_FUNCS = {
    "echo": tool_echo,
    "math": tool_math,
    "openai": tool_openai,
}

@app.post("/chat")
async def chat(request: Request):
    req = await request.json()
    tool = req.get("tool")
    message = req.get("message", "")
    if tool not in TOOLS:
        return {"error": "Tool not enabled for this satellite."}
    api_key = API_KEYS.get(tool)
    func = TOOL_FUNCS.get(tool)
    if not func:
        return {"error": "Tool not implemented."}
    return {"response": func(message, api_key)}

@app.get("/config")
async def get_config():
    return {
        "tools": TOOLS,
        "api_keys": API_KEYS,
        "openai_key": OPENAI_KEY,
    }
