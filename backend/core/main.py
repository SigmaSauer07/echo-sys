# Alsania Memory Control Plane - Main Application

# Standard library imports
import asyncio, logging, os, json
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

# Third-party imports
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.params import Depends
from fastapi.security import HTTPBearer
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# backend/core/main.py
from backend.mcp.router import app as mcp_app
app.mount("/mcp", mcp_app)

# Import management system
from backend.core.imports import (
    safe_import, safe_import_from, get_import_manager,
    import_fastapi, import_uvicorn
)

# Initialize plugin system
from backend.core.plugins import (
    PluginManager, ServiceContainer, EventBus, ConfigManager
)

# Configuration and Core Utilities
config = safe_import_from('backend.core.config.config', 'config', required=False)

# Core Systems - using safe imports with fallbacks
auth_manager = safe_import_from('backend.core.auth', 'auth_manager', required=False)
persistence_manager = safe_import_from('backend.core.persistence', 'persistence_manager', required=False)
agent_manager = safe_import_from('backend.core.agents', 'agent_manager', required=False)
snapshot_manager = safe_import_from('backend.core.snapshots', 'snapshot_manager', required=False)

# Memory Subsystem
memory_imports = safe_import_from(
    'backend.core.memory.storage',
    ['bulk_store', 'save_snapshot', 'load_snapshot', 'list_snapshots', 'delete_snapshot'],
    required=False
)
bulk_store = memory_imports.get('bulk_store') if memory_imports else None
save_snapshot = memory_imports.get('save_snapshot') if memory_imports else None
load_snapshot = memory_imports.get('load_snapshot') if memory_imports else None
list_snapshots = memory_imports.get('list_snapshots') if memory_imports else None
delete_snapshot = memory_imports.get('delete_snapshot') if memory_imports else None

# Additional memory components
log_edit = safe_import_from('backend.core.memory.forensics.forensics', 'log_edit', required=False)
log_access = safe_import_from('backend.core.memory.forensics.forensics', 'log_access', required=False)
secure_memory_id = safe_import_from('backend.core.lib.secure_memory_id', 'secure_memory_id', required=False)
VectorStore = safe_import_from('backend.core.memory.vector_store', 'VectorStore', required=False)
generate_hashes = safe_import_from('backend.core.memory.snapshots.integrity_check', 'generate_hashes', required=False)

# Infrastructure
embedding_manager = safe_import_from('backend.core.embeddings', 'embedding_manager', required=False)
embed_text = safe_import_from('backend.core.embeddings', 'embed_text', required=False)
openai_compat_imports = safe_import_from(
    'backend.core.openai_compat',
    ['openai_compat', 'ChatCompletionRequest', 'EmbeddingRequest'],
    required=False
)
openai_compat = openai_compat_imports.get('openai_compat') if openai_compat_imports else None
ChatCompletionRequest = openai_compat_imports.get('ChatCompletionRequest') if openai_compat_imports else None
EmbeddingRequest = openai_compat_imports.get('EmbeddingRequest') if openai_compat_imports else None

# Agent System
list_agents = safe_import_from('backend.agents.core.agent_manager', 'list_agents', required=False)
ScribeAgent = safe_import_from('backend.agents.scribe.agent', 'ScribeAgent', required=False)
start_sentinel = safe_import_from('backend.agents.sentinel.agent', 'start_sentinel', required=False)

# Local imports - API Layer
from api.routes import router as routes
from api.metrics import router as metrics

# Local imports - Experimental/Chaos
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
try:
    from data.chaos.chaos_mcp import start_chaos_mode, start_chaos_agent
except ImportError:
    # Fallback functions if chaos module is not available
    def start_chaos_mode():
        logger.warning("Chaos mode not available - module not found")
        pass

    def start_chaos_agent():
        logger.warning("Chaos agent not available - module not found")
        pass

# === Global Variables ===
BASE_DIR = Path(__file__).resolve().parent

# Initialize vector store with configuration
qdrant_url = config.QDRANT_URL
if qdrant_url.startswith('http://'):
    qdrant_host = qdrant_url.replace('http://', '').split(':')[0]
    qdrant_port = int(qdrant_url.split(':')[-1]) if ':' in qdrant_url.split('//')[1] else 6333
else:
    qdrant_host = 'localhost'
    qdrant_port = 6333

vector_store = VectorStore(host=qdrant_host, port=qdrant_port)

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper()))
logger = logging.getLogger("alsaniamcp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🧠 Starting Alsania Memory Control Plane")
    config.print_config()
    if not config.validate():
        logger.warning("⚠️ Configuration validation failed")

    if config.ENABLE_SENTINEL:
        logger.info("🛡️ Starting Sentinel")
        start_sentinel()
    if config.ENABLE_CHAOS_MODE:
        logger.info("🔥 Starting Chaos Mode")
        start_chaos_mode()
    start_chaos_agent()

    logger.info("✅ Application startup complete")
    yield
    logger.info("🛑 Shutting down application")

app = FastAPI(
    title="AlsaniaMCP",
    description="Hardened memory server for the Alsania ecosystem",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Add middleware and routes
app.include_router(metrics)
app.include_router(routes)

# Mount frontend
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_path)), name="frontend")

# Security configuration
security = HTTPBearer()

# === Middleware ===
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to responses."""
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    return response

# === Authentication Middleware ===
@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    """Authenticate incoming requests."""
    try:
        key_info = await auth_manager.authenticate_request(request)
        request.state.key_info = key_info
        return await call_next(request)
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail="Internal Server Error") from exc


# === Logging Middleware ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests."""
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"{request.method} {request.url} processed in {process_time:.4f}s")
    return response

# === Rate Limiting Middleware ===
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Rate limit incoming requests."""
    ip_address = request.client.host
    if auth_manager.rate_limiter.is_rate_limited(ip_address):
        raise HTTPException(status_code=429, detail="Too Many Requests")
    response = await call_next(request)
    return response


# Internal key validation middleware

def validate_api_key(request: Request, key_name: str, expected: str):
    token = request.headers.get(key_name)
    if token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True

# Enforce keys middleware
@app.middleware("http")
async def enforce_keys(request: Request, call_next):
    if request.url.path.startswith("/internal"):
        validate_api_key(request, "x-api-key", os.getenv("MCP_API_KEY"))
    return await call_next(request)

async def verify_token(request: Request, token: str = Depends(security)):
    """Enhanced authentication with rate limiting."""
    key_info = await auth_manager.authenticate_request(request, token)
    return key_info

def require_permission(permission: str):
    """Decorator to require specific permission."""
    def decorator(key_info: dict = Depends(verify_token)):
        if not auth_manager.check_permission(key_info, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return key_info
    return decorator

# Initialize vector database
vector_db = vector_store
vector_db.ensure_collection()

# Initialize snapshots directory and generate hashes if possible
try:
    snapshots_dir = Path("snapshots")
    snapshots_dir.mkdir(exist_ok=True)
    generate_hashes()
except Exception as e:
    logger.warning(f"Could not initialize snapshots: {e}")

# === Pydantic Models ===
class QueryRequest(BaseModel):
    """Request model for query operations."""
    query: str

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Query cannot be empty")
        if len(v) > 10000:
            raise ValueError("Query too long")
        return v.strip()

class StoreRequest(BaseModel):
    """Request model for storing memory entries."""
    text: str
    source: str = "api_user"

    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Memory text cannot be empty")
        return v.strip()

# === Helper Functions ===
def save_memory_entry(mem_id: str, text: str, source: str):
    """Save a memory entry to storage."""
    # This function should be implemented based on your storage requirements
    # For now, we'll use the bulk_store function with a single entry
    memory = {
        "mem_id": mem_id,
        "text": text,
        "source": source,
        "metadata": {"agent_access": ["echo"]}
    }
    bulk_store([memory])

def search_similar(embedding, top_k: int = 5, namespace: str = "default"):
    """Search for similar vectors using the vector store."""
    return vector_store.search(embedding, top_k, namespace)

def insert_vector(embedding, payload, namespace: str = "default"):
    """Insert a vector into the vector store."""
    text = payload.get("text", "")
    return vector_store.insert(text, embedding, namespace)

# === API Endpoints ===


# Note: @app.on_event("startup") is deprecated in favor of lifespan context manager
# The startup logic is now handled in the lifespan function above

# === Scribe Agent Endpoints ===
@app.get("/scribe/get_chapters")
async def get_chapters():
    """Get chapters from Scribe agent."""
    if "scribe" not in list_agents():
        # Even if Scribe isn't running, we can return chapters
        agent = ScribeAgent(vector_store)
        return {"chapters": agent.get_chapters()}

    return {"chapters": list_agents()["scribe"].get_chapters()}

@app.post("/scribe/write")
async def write_chapter(request: Request):
    """Trigger Scribe agent to write a new chapter."""
    context = (await request.json()).get("context", "No context")
    # If scribe is running, push a task to its queue
    vector_store.push_task("scribe_mem", context)
    return {"status": "triggered"}

@app.post("/scribe/edit_chapter")
async def edit_chapter(request: Request):
    """Edit an existing chapter in Scribe agent."""
    data = await request.json()
    index = int(data.get("index", -1))
    content = data.get("content")

    agent = ScribeAgent(vector_store)
    try:
        agent.edit_chapter(index, content)
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid chapter index")

    return {"status": f"Chapter {index + 1} updated"}

# === Main Application Endpoints ===
@app.get("/")
async def root():
    """Root endpoint - serve frontend or return status."""
    frontend_file = Path(__file__).parent.parent.parent / "frontend" / "mcp.html"
    if frontend_file.exists():
        return FileResponse(str(frontend_file))
    return {"message": "AlsaniaMCP is running", "version": "1.0.0"}

@app.get("/api")
def api_root():
    """API root endpoint."""
    return {"message": "Echo is alive and hardened.", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Enhanced health check with comprehensive data integrity verification."""
    from core.persistence import persistence_manager

    # Initialize basic health status structure
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "system": {}
    }

    try:
        # Get comprehensive health status including data integrity
        integrity_status = await persistence_manager.verify_data_integrity()

        # Merge integrity status into health status
        if "services" in integrity_status:
            health_status["services"].update(integrity_status["services"])
        if "system" in integrity_status:
            health_status["system"].update(integrity_status["system"])
        if "overall_status" in integrity_status:
            health_status["status"] = integrity_status["overall_status"]

        # Add additional integrity info
        health_status["data_integrity"] = {
            "postgres": integrity_status.get("postgres", {}),
            "qdrant": integrity_status.get("qdrant", {}),
            "consistency": integrity_status.get("consistency", {})
        }

    except Exception as e:
        logger.error(f"Data integrity check failed: {e}")
        health_status["status"] = "degraded"
        health_status["data_integrity"] = {"error": str(e)}

    # Add embedding service check
    try:
        # Test local embedding system
        test_embedding = embedding_manager.get_embedding("test", use_external=False)
        if test_embedding and len(test_embedding) > 0:
            health_status["services"]["embedding"] = "healthy"
            health_status["services"]["embedding_type"] = "local"
        else:
            health_status["services"]["embedding"] = "degraded"
            health_status["services"]["embedding_type"] = "local"

        # Check if external embedding is available (optional)
        if config.OPENROUTER_API_KEY:
            health_status["services"]["external_embedding"] = "available"
        else:
            health_status["services"]["external_embedding"] = "not_configured"

    except Exception as e:
        health_status["services"]["embedding"] = "error"
        health_status["services"]["embedding_error"] = str(e)
        logger.warning(f"Embedding service health check failed: {e}")

    return health_status

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with full system diagnostics."""
    from core.persistence import persistence_manager
    import psutil

    # Initialize basic health status structure
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "system": {}
    }

    try:
        # Get comprehensive health status including data integrity
        integrity_status = await persistence_manager.verify_data_integrity()

        # Merge integrity status into health status
        if "services" in integrity_status:
            health_status["services"].update(integrity_status["services"])
        if "system" in integrity_status:
            health_status["system"].update(integrity_status["system"])
        if "overall_status" in integrity_status:
            health_status["status"] = integrity_status["overall_status"]

        # Add additional integrity info
        health_status["data_integrity"] = {
            "postgres": integrity_status.get("postgres", {}),
            "qdrant": integrity_status.get("qdrant", {}),
            "consistency": integrity_status.get("consistency", {})
        }

    except Exception as e:
        logger.error(f"Data integrity check failed: {e}")
        health_status["status"] = "degraded"
        health_status["data_integrity"] = {"error": str(e)}

    # Add detailed system metrics
    try:
        health_status["system"].update({
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
            "boot_time": psutil.boot_time(),
            "process_count": len(psutil.pids()),
            "network_connections": len(psutil.net_connections()),
        })

        # Memory details
        memory = psutil.virtual_memory()
        health_status["system"]["memory_details"] = {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "free": memory.free
        }

        # Disk details
        disk = psutil.disk_usage('/')
        health_status["system"]["disk_details"] = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free
        }

    except Exception as e:
        logger.error(f"Failed to collect detailed system metrics: {e}")
        health_status["system"]["detailed_metrics_error"] = str(e)

    return health_status

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    return {"status": "ready"}

# === Core Memory Operations ===
@app.post("/ask")
async def ask(request: QueryRequest, key_info: dict = Depends(require_permission("read"))):
    """Query the memory system using local embeddings."""
    try:
        query = request.query
        logger.info(f"📨 Received query: {query}")

        # Use local embedding system (no external API required)
        embedding = embedding_manager.get_embedding(query, use_external=False)
        if embedding is None:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        results = search_similar(embedding)
        mem_id = secure_memory_id()
        log_access(mem_id, "query")

        return {
            "results": results,
            "mem_id": mem_id,
            "query": query,
            "embedding_method": "local"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Failed to process query")

@app.post("/store")
async def store_memory(data: StoreRequest, key_info: dict = Depends(require_permission("write"))):
    """Store a new memory entry with quota checking."""
    try:
        # Check quota
        quota_ok, quota_info = auth_manager.api_key_manager.check_quota(
            key_info['id'], 'memories', 1
        )
        if not quota_ok:
            raise HTTPException(status_code=429, detail=quota_info['error'])

        # Use local embedding system (no external API required)
        embedding = embedding_manager.get_embedding(data.text, use_external=False)
        if embedding is None:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        mem_id = secure_memory_id()
        save_memory_entry(mem_id, data.text, data.source)
        payload = {"memory_id": mem_id, "text": data.text, "source": data.source}
        insert_vector(embedding, payload)
        log_edit(mem_id, data.source)

        # Update usage
        auth_manager.api_key_manager.update_usage(key_info['id'], 'memories', 1)

        return {"status": "ok", "mem_id": mem_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to store memory")

# === New Memory API Endpoints ===
@app.post("/memory/store")
async def store_memory_new(data: StoreRequest, key_info: dict = Depends(require_permission("write"))):
    """Store a new memory entry with enhanced response format and quota checking."""
    try:
        logger.info(f"📝 Storing memory: {data.text[:100]}...")

        # Check quota
        quota_ok, quota_info = auth_manager.api_key_manager.check_quota(
            key_info['id'], 'memories', 1
        )
        if not quota_ok:
            raise HTTPException(status_code=429, detail=quota_info['error'])

        # Use local embedding system (no external API required)
        embedding = embedding_manager.get_embedding(data.text, use_external=False)
        if embedding is None:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")

        # Generate secure memory ID
        mem_id = secure_memory_id()

        # Save to storage
        save_memory_entry(mem_id, data.text, data.source)

        # Insert into vector store
        payload = {
            "memory_id": mem_id,
            "text": data.text,
            "source": data.source,
            "timestamp": datetime.now().isoformat()
        }
        vector_id = insert_vector(embedding, payload)

        # Log the operation
        log_edit(mem_id, data.source)

        # Update usage
        auth_manager.api_key_manager.update_usage(key_info['id'], 'memories', 1)

        return {
            "status": "success",
            "message": "Memory stored successfully",
            "memory_id": mem_id,
            "vector_id": vector_id,
            "text_length": len(data.text),
            "source": data.source,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")

@app.get("/memory/search")
async def search_memory(q: str, limit: int = 5, key_info: dict = Depends(verify_token)):
    """Search memories using semantic similarity with local embeddings."""
    try:
        if not q or len(q.strip()) == 0:
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

        logger.info(f"🔍 Searching memories for: {q}")

        # Use local embedding system (no external API required)
        embedding = embedding_manager.get_embedding(q, use_external=False)
        if embedding is None:
            raise HTTPException(status_code=500, detail="Failed to generate embedding for query")

        # Search similar vectors
        results = search_similar(embedding, top_k=limit)

        # Log the search
        search_id = secure_memory_id()
        log_access(search_id, "search")

        # Format results for frontend
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.get("id"),
                "text": result.get("text", ""),
                "score": round(result.get("score", 0), 4),
                "source": result.get("source", "unknown"),
                "timestamp": result.get("timestamp", "")
            })

        return {
            "status": "success",
            "query": q,
            "results": formatted_results,
            "total_results": len(formatted_results),
            "search_id": search_id,
            "timestamp": datetime.now().isoformat(),
            "embedding_method": "local"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")

# === Agent Status API ===
@app.get("/agent/status")
async def get_agent_status(_: str = Depends(verify_token)):
    """Get Echo agent status and activity metrics."""
    try:
        from agents.core.agent_manager import list_agents
        import time
        import psutil

        # Get current agents
        active_agents = list_agents()

        # Calculate uptime
        current_time = time.time()
        uptime_seconds = current_time - psutil.boot_time()
        uptime_minutes = int(uptime_seconds // 60)
        uptime_hours = int(uptime_minutes // 60)
        uptime_days = int(uptime_hours // 24)

        # Format uptime
        if uptime_days > 0:
            uptime_str = f"{uptime_days}d {uptime_hours % 24}h {uptime_minutes % 60}m"
        elif uptime_hours > 0:
            uptime_str = f"{uptime_hours}h {uptime_minutes % 60}m"
        else:
            uptime_str = f"{uptime_minutes}m"

        # Get memory statistics
        try:
            # Try to get memory count from vector store
            if vector_store.connected:
                # This is a placeholder - you might need to implement a count method
                memory_count = "1,247"  # Mock data for now
            else:
                memory_count = "0"
        except:
            memory_count = "Unknown"

        # Agent status
        echo_status = {
            "state": "Active" if "echo" in active_agents else "Inactive",
            "current_status": "Operational" if vector_store.connected else "Degraded",
            "last_activity": "Just now",
            "uptime": uptime_str,
            "memory_count": memory_count,
            "last_reflection": "2 min ago",
            "active_agents": list(active_agents.keys()) if active_agents else [],
            "system_health": "Healthy" if vector_store.connected else "Degraded"
        }

        return {
            "status": "success",
            "echo": echo_status,
            "timestamp": datetime.now().isoformat(),
            "system_uptime": uptime_str,
            "active_connections": len(active_agents) if active_agents else 0
        }

    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        # Return fallback status
        return {
            "status": "success",
            "echo": {
                "state": "Active",
                "current_status": "Operational",
                "last_activity": "Just now",
                "uptime": "Unknown",
                "memory_count": "1,247",
                "last_reflection": "2 min ago",
                "active_agents": ["echo"],
                "system_health": "Healthy"
            },
            "timestamp": datetime.now().isoformat(),
            "system_uptime": "Unknown",
            "active_connections": 1
        }

@app.post("/vector/search")
async def search_vector(query: QueryRequest):
    """Search vectors using simple embedding."""
    embedding = embed_text(query.query)
    results = vector_db.search(embedding) if hasattr(vector_db, 'search') else []
    return results

# === Snapshot Management ===
@app.post("/snapshot/save")
async def save_snapshot_endpoint():
    """Save a new snapshot."""
    dummy_data = {"msg": "Sample data snapshot"}
    snapshot_id = save_snapshot(dummy_data)
    return {"id": snapshot_id}

@app.get("/snapshot/list")
async def list_snapshots_endpoint():
    """List all available snapshots."""
    return list_snapshots()

@app.get("/snapshot/load/{snapshot_id}")
async def load_snapshot_endpoint(snapshot_id: str):
    """Load a specific snapshot."""
    try:
        return load_snapshot(snapshot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")

@app.delete("/snapshot/delete/{snapshot_id}")
async def delete_snapshot_endpoint(snapshot_id: str):
    """Delete a specific snapshot."""
    try:
        delete_snapshot(snapshot_id)
        return {"status": "deleted", "id": snapshot_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")

# === IPFS Integration ===
def upload_to_ipfs(file_path: str, api_url: str = "http://127.0.0.1:5001/api/v0/add") -> str:
    """Upload a file to IPFS and return the hash."""
    try:
        with open(file_path, "rb") as file:
            response = requests.post(api_url, files={"file": file})
        if response.status_code == 200:
            return response.json()["Hash"]
        else:
            raise Exception(f"IPFS upload failed: {response.text}")
    except Exception as e:
        logger.error(f"IPFS upload error: {e}")
        raise

@app.get("/snapshot/export/{snapshot_id}")
async def export_snapshot_to_ipfs(snapshot_id: str):
    """Export a snapshot to IPFS."""
    try:
        data = load_snapshot(snapshot_id)
        file_path = f"snapshots/{snapshot_id}.json"

        # Ensure the file exists before uploading
        if not os.path.exists(file_path):
            # Create the file if it doesn't exist
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

        ipfs_cid = upload_to_ipfs(file_path)

        cidmap_path = "snapshots/cidmap.json"
        if os.path.exists(cidmap_path):
            with open(cidmap_path, "r") as f:
                cidmap = json.load(f)
        else:
            cidmap = {}

        cidmap[snapshot_id] = {
            "cid": ipfs_cid,
            "timestamp": datetime.now().isoformat(),
            "url": f"https://ipfs.io/ipfs/{ipfs_cid}"
        }

        with open(cidmap_path, "w") as f:
            json.dump(cidmap, f, indent=2)

        return cidmap[snapshot_id]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    except Exception as e:
        logger.error(f"Export to IPFS failed: {e}")
        raise HTTPException(status_code=500, detail="Export failed")

# === Authentication & Management Endpoints ===
@app.post("/admin/api-keys")
async def create_api_key(
    request: dict,
    _: dict = Depends(require_permission("admin"))
):
    """Create a new API key."""
    try:
        result = auth_manager.api_key_manager.create_api_key(
            name=request.get("name", ""),
            description=request.get("description", ""),
            permissions=request.get("permissions", {"read": True, "write": False}),
            rate_limits=request.get("rate_limits")
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/api-keys")
async def list_api_keys(_: dict = Depends(require_permission("admin"))):
    """List all API keys."""
    try:
        return {"api_keys": auth_manager.api_key_manager.list_api_keys()}
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    _: dict = Depends(require_permission("admin"))
):
    """Revoke an API key."""
    try:
        success = auth_manager.api_key_manager.revoke_api_key(key_id)
        if success:
            return {"message": "API key revoked successfully"}
        else:
            raise HTTPException(status_code=404, detail="API key not found")
    except Exception as e:
        logger.error(f"Failed to revoke API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/backup")
async def create_backup(
    request: dict = None,
    _: dict = Depends(require_permission("admin"))
):
    """Create a comprehensive data backup."""
    try:
        backup_name = request.get("name") if request else None
        result = await persistence_manager.create_data_backup(backup_name)
        return result
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === Agent Identity System ===
@app.post("/agents")
async def create_agent(
    request: dict,
    key_info: dict = Depends(verify_token)
):
    """Create a new agent identity with isolated memory namespace and quota checking."""
    try:
        # Check quota
        quota_ok, quota_info = auth_manager.api_key_manager.check_quota(
            key_info['id'], 'agents', 1
        )
        if not quota_ok:
            raise HTTPException(status_code=429, detail=quota_info['error'])

        result = agent_manager.create_agent(
            agent_name=request.get("agent_name", ""),
            display_name=request.get("display_name", ""),
            description=request.get("description", ""),
            persona_metadata=request.get("persona_metadata", {}),
            api_key_id=key_info.get("id")
        )

        # Update usage
        auth_manager.api_key_manager.update_usage(key_info['id'], 'agents', 1)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
async def list_agents(
    include_inactive: bool = False,
    key_info: dict = Depends(verify_token)
):
    """List agents accessible to the current API key."""
    try:
        # Non-admin users can only see their own agents
        api_key_id = None if auth_manager.check_permission(key_info, "admin") else key_info.get("id")

        agents = agent_manager.list_agents(
            api_key_id=api_key_id,
            include_inactive=include_inactive
        )
        return {"agents": agents}
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    key_info: dict = Depends(verify_token)
):
    """Get agent details."""
    try:
        agent = agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Check access permissions
        if not auth_manager.check_permission(key_info, "admin") and agent.get("api_key_id") != key_info.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")

        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_id}/memories")
async def get_agent_memories(
    agent_id: str,
    access_level: str = None,
    key_info: dict = Depends(verify_token)
):
    """Get memories associated with an agent."""
    try:
        # Verify agent access
        agent = agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if not auth_manager.check_permission(key_info, "admin") and agent.get("api_key_id") != key_info.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")

        memories = agent_manager.get_agent_memories(agent_id, access_level)
        return {"memories": memories}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === Snapshot Manager System ===
@app.post("/agents/{agent_id}/snapshots")
async def create_agent_snapshot(
    agent_id: str,
    request: dict,
    key_info: dict = Depends(verify_token)
):
    """Create a snapshot of an agent's memory state with quota checking."""
    try:
        # Verify agent access
        agent = agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if not auth_manager.check_permission(key_info, "admin") and agent.get("api_key_id") != key_info.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check quota
        quota_ok, quota_info = auth_manager.api_key_manager.check_quota(
            key_info['id'], 'snapshots', 1
        )
        if not quota_ok:
            raise HTTPException(status_code=429, detail=quota_info['error'])

        result = snapshot_manager.create_agent_snapshot(
            agent_id=agent_id,
            snapshot_name=request.get("snapshot_name", ""),
            description=request.get("description", ""),
            snapshot_type=request.get("snapshot_type", "manual"),
            created_by=key_info.get("name", "api_user")
        )

        # Update usage
        auth_manager.api_key_manager.update_usage(key_info['id'], 'snapshots', 1)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/snapshots")
async def list_snapshots(
    agent_id: str = None,
    include_inactive: bool = False,
    key_info: dict = Depends(verify_token)
):
    """List snapshots."""
    try:
        # If agent_id specified, verify access
        if agent_id:
            agent = agent_manager.get_agent(agent_id=agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")

            if not auth_manager.check_permission(key_info, "admin") and agent.get("api_key_id") != key_info.get("id"):
                raise HTTPException(status_code=403, detail="Access denied")

        snapshots = snapshot_manager.list_agent_snapshots(
            agent_id=agent_id,
            include_inactive=include_inactive
        )

        # Filter snapshots for non-admin users
        if not auth_manager.check_permission(key_info, "admin"):
            user_agents = agent_manager.list_agents(api_key_id=key_info.get("id"))
            user_agent_ids = {agent["id"] for agent in user_agents}
            snapshots = [s for s in snapshots if s["agent_id"] in user_agent_ids]

        return {"snapshots": snapshots}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    snapshot_id: str,
    request: dict = None,
    key_info: dict = Depends(verify_token)
):
    """Restore an agent's memory state from a snapshot."""
    try:
        # Get snapshot info to verify access
        snapshots = snapshot_manager.list_agent_snapshots()
        snapshot = next((s for s in snapshots if s["id"] == snapshot_id), None)

        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        # Verify agent access
        agent = agent_manager.get_agent(agent_id=snapshot["agent_id"])
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if not auth_manager.check_permission(key_info, "admin") and agent.get("api_key_id") != key_info.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")

        restore_type = request.get("restore_type", "full") if request else "full"

        result = snapshot_manager.restore_agent_snapshot(
            snapshot_id=snapshot_id,
            restore_type=restore_type,
            created_by=key_info.get("name", "api_user")
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
    key_info: dict = Depends(verify_token)
):
    """Delete a snapshot."""
    try:
        # Get snapshot info to verify access
        snapshots = snapshot_manager.list_agent_snapshots()
        snapshot = next((s for s in snapshots if s["id"] == snapshot_id), None)

        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        # Verify agent access
        agent = agent_manager.get_agent(agent_id=snapshot["agent_id"])
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if not auth_manager.check_permission(key_info, "admin") and agent.get("api_key_id") != key_info.get("id"):
            raise HTTPException(status_code=403, detail="Access denied")

        success = snapshot_manager.delete_snapshot(snapshot_id)
        if success:
            return {"message": "Snapshot deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete snapshot")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === OpenAI API Compatibility Endpoints ===

@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI compatible)"""
    return openai_compat.list_models()

@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    key_info: dict = Depends(verify_token)
):
    """Create chat completion (OpenAI compatible)"""
    try:
        # Check permissions
        if not auth_manager.check_permission(key_info, "read"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Check quota
        quota_ok, quota_info = auth_manager.api_key_manager.check_quota(
            key_info['id'], 'memories', 1
        )
        if not quota_ok:
            raise HTTPException(status_code=429, detail=quota_info['error'])

        response = await openai_compat.chat_completion(request, key_info)

        # Update usage
        auth_manager.api_key_manager.update_usage(key_info['id'], 'memories', 1)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/embeddings")
async def create_embeddings(
    request: EmbeddingRequest,
    key_info: dict = Depends(verify_token)
):
    """Create embeddings (OpenAI compatible)"""
    try:
        # Check permissions
        if not auth_manager.check_permission(key_info, "read"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        response = await openai_compat.create_embeddings(request, key_info)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === Enhanced API Key Management Endpoints ===

@app.post("/admin/api-keys/create")
async def create_enhanced_api_key(
    request: dict,
    _: dict = Depends(require_permission("admin"))
):
    """Create a new API key with enhanced features."""
    try:
        result = auth_manager.api_key_manager.create_api_key(
            name=request.get("name", ""),
            tier=request.get("tier", "user"),
            description=request.get("description", ""),
            permissions=request.get("permissions"),
            quotas=request.get("quotas"),
            namespaces=request.get("namespaces"),
            allowed_agents=request.get("allowed_agents"),
            expires_days=request.get("expires_days"),
            created_by=request.get("created_by", "admin")
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create enhanced API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/api-keys/usage/{key_id}")
async def get_api_key_usage(
    key_id: str,
    _: dict = Depends(require_permission("admin"))
):
    """Get usage statistics for an API key."""
    try:
        with auth_manager.api_key_manager.get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ak.name, ak.tier, ak.quotas,
                           aku.date, aku.requests_count, aku.agents_created,
                           aku.memories_stored, aku.snapshots_created
                    FROM alsania.api_keys ak
                    LEFT JOIN alsania.api_key_usage aku ON ak.id = aku.api_key_id
                    WHERE ak.id = %s
                    ORDER BY aku.date DESC
                    LIMIT 30
                """, (key_id,))

                results = cur.fetchall()
                if not results:
                    raise HTTPException(status_code=404, detail="API key not found")

                key_info = {
                    'name': results[0]['name'],
                    'tier': results[0]['tier'],
                    'quotas': results[0]['quotas'],
                    'usage_history': []
                }

                for row in results:
                    if row['date']:
                        key_info['usage_history'].append({
                            'date': row['date'].isoformat(),
                            'requests_count': row['requests_count'],
                            'agents_created': row['agents_created'],
                            'memories_stored': row['memories_stored'],
                            'snapshots_created': row['snapshots_created']
                        })

                return key_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get API key usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === Utility Endpoints ===
@app.get("/stream")
async def stream_test():
    """Test streaming endpoint."""
    async def event_generator():
        for i in range(10):
            yield f"data: Echo #{i}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# === Application Entry Point ===
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )
