<<<<<<< HEAD
# echo-sys
mcp and ai agent system 
=======
# Alsania MCP Hybrid System Documentation

## Overview
This system is a modular, hybrid MCP (Model Context Protocol) server that can spawn and manage satellite MCP servers. Each server can be customized with tools, API keys, and access control. The system is designed for extensibility, agent collaboration, and remote integration (e.g., with VS Code extensions).

---

## Core Server Features
- **Unified API**: `/chat`, `/remote`, `/tools`, `/spawn_satellite`, `/satellites`, `/satellite/{port}`
- **Agent Management**: Dynamically loads agents from `backend/agents/`.
- **Global Tools**: Built-in tools like `echo`, `math`, `upper`, `lower`, `date`, `random`.
- **OpenAI-Compatible API Key Management**: Set and get keys for core and satellites.
- **Remote Access**: Secure `/remote` endpoint for non-API-key clients (e.g., VS Code extensions).
- **Access Control**: Shared secret and rate limiting for `/remote`.

---

## Satellite Servers
- **Customizable**: Spawn with selected tools and API keys.
- **Remote Endpoint**: `/remote` for tool access, no API key required (unless you add it).
- **Config Endpoint**: `/config` returns current tool and key settings.

---

## How to Use

### 1. Start the Core Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8050
```

### 2. List Available Tools
```bash
curl http://127.0.0.1:8050/tools
```

### 3. Chat with Agents or Tools
```bash
curl -X POST http://127.0.0.1:8050/chat -H 'Content-Type: application/json' -d '{"agent": "echo", "message": "Hello!"}'
# or
curl -X POST http://127.0.0.1:8050/chat -H 'Content-Type: application/json' -d '{"tool": "math", "message": "2+2"}'
```

### 4. Remote Access (e.g., from VS Code Extension)
```bash
curl -X POST http://127.0.0.1:8050/remote -H 'Content-Type: application/json' -d '{"secret": "changeme", "tool": "echo", "message": "Hello from VS Code!"}'
```
- Set the `REMOTE_SECRET` environment variable to change the shared secret.

### 5. Spawn a Satellite Server
```bash
curl -X POST http://127.0.0.1:8050/spawn_satellite -H 'Content-Type: application/json' -d '{"tools": ["echo", "math"], "api_keys": {"openai": "sk-..."}, "openai_key": "sk-...", "port": 9001}'
```
- The satellite will run on the specified port (default: 9000+N).

### 6. Use a Satellite Server
```bash
curl -X POST http://127.0.0.1:9001/remote -H 'Content-Type: application/json' -d '{"tool": "echo", "message": "Hi from satellite!"}'
```
- See `/config` on the satellite for its current settings.

### 7. Manage Satellites
- List: `GET /satellites`
- Get config: `GET /satellite/{port}`
- Stop: `POST /satellite/{port}/stop`
- Update: `POST /satellite/{port}/update` (with new tools, keys, etc.)

---

## Agent Collaboration
- All agents must implement a `respond(message, config)` function.
- Agents can communicate via the core server by sending messages to `/chat` with the target agent name.

---

## Security & Best Practices
- Change the `REMOTE_SECRET` for production.
- Use rate limiting and logging to monitor remote access.
- Only expose necessary endpoints to the public.
- Review and update agent code to follow the `respond` interface.

---

## Extending the System
- Add new tools by defining a function and adding it to `GLOBAL_TOOLS` (core) or `TOOL_FUNCS` (satellite).
- Add new agents by placing them in `backend/agents/` with a `respond` function and a `config.json`.
- Customize satellite servers by editing `backend/satellite_template.py`.

---

## Troubleshooting
- If you see errors, check the logs and ensure all imports and definitions are in the correct order.
- Use the `/tools` endpoint to verify available tools.
- Use `/config` on satellites to verify their setup.

---

## Contact & Support
For questions or contributions, see the project README or contact the maintainer.
>>>>>>> 0e71de3 (Auto-commit: 224 added, 1 modified files)
# echo-sys
