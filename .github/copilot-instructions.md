# 🧠 Copilot Instructions for the Echo System

This document provides essential guidance for AI coding agents to be productive in the Echo System codebase. Follow these instructions to understand the architecture, workflows, and conventions specific to this project.

---

## 📜 Big Picture Architecture

The Echo System is a modular, hybrid MCP (Model Context Protocol) server designed for:
- **Extensibility**: Dynamically load agents and tools.
- **Agent Collaboration**: Agents communicate via the core server.
- **Remote Integration**: Supports external tools like VS Code extensions.

### Key Components:
1. **Core Server**:
   - Unified API: `/chat`, `/remote`, `/tools`, `/spawn_satellite`, `/satellites`, `/satellite/{port}`.
   - Manages agents and tools.
   - Located in `backend/core/`.

2. **Agents**:
   - Modular AI components in `backend/agents/`.
   - Each agent implements a `respond(message, config)` function.

3. **Satellite Servers**:
   - Spawned dynamically with selected tools and API keys.
   - Configurable via `/config` endpoint.

4. **Frontend**:
   - Located in `frontend/client/`.
   - Built with HTML, JS, and CSS (no React unless explicitly required).

5. **Infrastructure**:
   - Dockerized setup in `infra/docker/`.
   - Database initialization scripts in `infra/database/`.

---

## 🛠️ Developer Workflows

### 1. Start the Core Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8050
```

### 2. Run Tests
```bash
pytest
```
- Test files are located in `backend/tests/`.

### 3. Debugging
- Use the `/tools` endpoint to verify available tools.
- Check logs for errors and ensure imports are correct.

### 4. Spawn a Satellite Server
```bash
curl -X POST http://127.0.0.1:8050/spawn_satellite -H 'Content-Type: application/json' -d '{"tools": ["echo", "math"], "api_keys": {"openai": "sk-..."}, "port": 9001}'
```

---

## 📏 Project-Specific Conventions

1. **File Structure**:
   - Agents: `backend/agents/`
   - Tools: `backend/tools/`
   - Core logic: `backend/core/`
   - Frontend: `frontend/client/`

2. **Coding Standards**:
   - Follow the `respond` interface for agents.
   - Use `config.json` for agent metadata.
   - Avoid React unless explicitly required.

3. **Testing**:
   - Write unit tests for all agents and tools.
   - Place tests in `backend/tests/`.

---

## 🔗 Integration Points

1. **External Dependencies**:
   - OpenAI-compatible API keys for tools.
   - IPFS for metadata storage.

2. **Cross-Component Communication**:
   - Agents communicate via `/chat` endpoint.
   - Satellite servers use `/remote` for tool access.

---

## 🚫 Things to Avoid
- ❌ Using React, Next.js, or Vite without explicit permission.
- ❌ Retaining memory unless explicitly allowed.
- ❌ Modifying core system logic without approval.

---

## 📚 References
- [README.md](../README.md): Project overview and usage.
- [alsania-rules.md](../.github/alsania-rules/alsania-rules.md): General project rules.
- [alsania-ai-alignment.md](../.github/alsania-rules/alsania-ai-alignment.md): AI alignment protocol.

For questions or contributions, contact the maintainer.