#!/usr/bin/env python3
"""
Echo Core - The Alsania Brain
Platform-wide integration with continuous learning and never-terminating orchestration
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config.config import config

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper()))
logger = logging.getLogger("echo-core")

# Create FastAPI app
app = FastAPI(
    title="Echo Core - Alsania Brain",
    description="Platform-wide integration with continuous learning",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize Echo Core on startup"""
    logger.info("🧠 Echo Core starting up...")
    logger.info(f"   Mode: {os.getenv('ECHO_MODE', 'core')}")
    logger.info(f"   Learning: {os.getenv('ECHO_LEARNING_ENABLED', 'true')}")
    logger.info(f"   Persistence: {os.getenv('ECHO_PERSISTENCE_ENABLED', 'true')}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Echo Core shutting down...")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Echo Core",
        "version": "1.0.0",
        "status": "active",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "echo-core",
        "timestamp": datetime.now().isoformat(),
        "mode": os.getenv('ECHO_MODE', 'core'),
        "learning_enabled": os.getenv('ECHO_LEARNING_ENABLED', 'true'),
        "persistence_enabled": os.getenv('ECHO_PERSISTENCE_ENABLED', 'true')
    }

@app.get("/status")
async def status():
    """Detailed status endpoint"""
    return {
        "echo_core": {
            "status": "active",
            "mode": os.getenv('ECHO_MODE', 'core'),
            "id": os.getenv('ECHO_ID', 'echo-core-001'),
            "role": os.getenv('ECHO_ROLE', 'platform-orchestrator')
        },
        "learning": {
            "enabled": os.getenv('ECHO_LEARNING_ENABLED', 'true') == 'true',
            "persistence": os.getenv('ECHO_PERSISTENCE_ENABLED', 'true') == 'true'
        },
        "platform": {
            "cross_system_awareness": os.getenv('ECHO_CROSS_SYSTEM_AWARENESS', 'true') == 'true',
            "never_terminate": os.getenv('ECHO_NEVER_TERMINATE', 'true') == 'true',
            "evolution_mode": os.getenv('ECHO_EVOLUTION_MODE', 'continuous')
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/learn")
async def learn(data: dict):
    """Learning endpoint for continuous improvement"""
    logger.info(f"📚 Learning from data: {data.get('type', 'unknown')}")
    return {
        "status": "learning",
        "data_type": data.get('type', 'unknown'),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/platform/status")
async def platform_status():
    """Platform-wide status check"""
    return {
        "platform": {
            "name": "AlsaniaMCP",
            "echo_core": "active",
            "agents": "managed",
            "memory": "operational",
            "learning": "continuous"
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Echo Core - Alsania Brain")
    parser.add_argument("--mode", default="core", help="Echo mode")
    parser.add_argument("--never-terminate", action="store_true", help="Never terminate")
    
    args = parser.parse_args()
    
    # Set environment variables from args
    if args.mode:
        os.environ['ECHO_MODE'] = args.mode
    if args.never_terminate:
        os.environ['ECHO_NEVER_TERMINATE'] = 'true'
    
    # Start the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8060,
        reload=False,
        log_level=config.LOG_LEVEL.lower()
    ) 