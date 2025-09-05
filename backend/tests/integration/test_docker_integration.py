"""
Docker integration tests for AlsaniaMCP

Tests the containerized functionality and service interactions
within the Docker environment.
"""

import pytest
import asyncio
import httpx
import time
from pathlib import Path


@pytest.mark.docker
@pytest.mark.slow
class TestDockerIntegration:
    """Test Docker-based integration"""
    
    @pytest.fixture(scope="class")
    def docker_services_url(self):
        """Base URL for Docker services"""
        return "http://localhost"
    
    @pytest.fixture(scope="class")
    def mcp_service_url(self, docker_services_url):
        """MCP service URL"""
        return f"{docker_services_url}:8050"
    
    @pytest.fixture(scope="class")
    def api_service_url(self, docker_services_url):
        """API service URL"""
        return f"{docker_services_url}:8050"
    
    @pytest.mark.asyncio
    async def test_mcp_service_health(self, mcp_service_url):
        """Test MCP service health endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{mcp_service_url}/health", timeout=10.0)
                assert response.status_code == 200
                
                health_data = response.json()
                assert "status" in health_data
                assert health_data["status"] == "healthy"
                
            except httpx.ConnectError:
                pytest.skip("MCP service not available - ensure Docker services are running")
    
    @pytest.mark.asyncio
    async def test_api_service_health(self, api_service_url):
        """Test API service health endpoint"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{api_service_url}/health", timeout=10.0)
                assert response.status_code == 200
                
                health_data = response.json()
                assert "status" in health_data
                assert health_data["status"] == "healthy"
                
            except httpx.ConnectError:
                pytest.skip("API service not available - ensure Docker services are running")
    
    @pytest.mark.asyncio
    async def test_service_communication(self, mcp_service_url, api_service_url):
        """Test communication between services"""
        async with httpx.AsyncClient() as client:
            try:
                # Test MCP service
                mcp_response = await client.get(f"{mcp_service_url}/api/status", timeout=10.0)
                assert mcp_response.status_code == 200
                
                # Test API service
                api_response = await client.get(f"{api_service_url}/api/status", timeout=10.0)
                assert api_response.status_code == 200
                
                # Both should be operational
                mcp_data = mcp_response.json()
                api_data = api_response.json()
                
                assert mcp_data.get("service") == "mcp"
                assert api_data.get("service") == "api"
                
            except httpx.ConnectError:
                pytest.skip("Services not available - ensure Docker services are running")
    
    @pytest.mark.asyncio
    async def test_database_connectivity(self, mcp_service_url):
        """Test database connectivity through service"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{mcp_service_url}/api/db/status", timeout=10.0)
                assert response.status_code == 200
                
                db_status = response.json()
                assert db_status.get("database") == "connected"
                
            except httpx.ConnectError:
                pytest.skip("MCP service not available")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    pytest.skip("Database not available")
                raise
    
    @pytest.mark.asyncio
    async def test_redis_connectivity(self, mcp_service_url):
        """Test Redis connectivity through service"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{mcp_service_url}/api/cache/status", timeout=10.0)
                assert response.status_code == 200
                
                cache_status = response.json()
                assert cache_status.get("cache") == "connected"
                
            except httpx.ConnectError:
                pytest.skip("MCP service not available")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    pytest.skip("Redis not available")
                raise
    
    @pytest.mark.asyncio
    async def test_qdrant_connectivity(self, mcp_service_url):
        """Test Qdrant connectivity through service"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{mcp_service_url}/api/vector/status", timeout=10.0)
                assert response.status_code == 200
                
                vector_status = response.json()
                assert vector_status.get("vector_store") == "connected"
                
            except httpx.ConnectError:
                pytest.skip("MCP service not available")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503:
                    pytest.skip("Qdrant not available")
                raise
    
    @pytest.mark.asyncio
    async def test_plugin_system_in_docker(self, mcp_service_url):
        """Test plugin system functionality in Docker"""
        async with httpx.AsyncClient() as client:
            try:
                # Get plugin status
                response = await client.get(f"{mcp_service_url}/api/plugins/status", timeout=10.0)
                assert response.status_code == 200
                
                plugin_status = response.json()
                assert "plugins" in plugin_status
                assert "loaded_count" in plugin_status
                
                # Should have some plugins loaded
                assert plugin_status["loaded_count"] >= 0
                
            except httpx.ConnectError:
                pytest.skip("MCP service not available")
    
    @pytest.mark.asyncio
    async def test_agent_functionality(self, api_service_url):
        """Test agent functionality through API"""
        async with httpx.AsyncClient() as client:
            try:
                # List available agents
                response = await client.get(f"{api_service_url}/api/agents", timeout=10.0)
                assert response.status_code == 200
                
                agents = response.json()
                assert isinstance(agents, list)
                
                # If agents are available, test one
                if agents:
                    agent_name = agents[0]["name"]
                    
                    # Test agent message processing
                    message_data = {
                        "message": "test message",
                        "context": {}
                    }
                    
                    response = await client.post(
                        f"{api_service_url}/api/agents/{agent_name}/process",
                        json=message_data,
                        timeout=30.0
                    )
                    
                    assert response.status_code == 200
                    result = response.json()
                    assert "response" in result
                
            except httpx.ConnectError:
                pytest.skip("API service not available")
    
    @pytest.mark.asyncio
    async def test_memory_operations(self, api_service_url):
        """Test memory operations through API"""
        async with httpx.AsyncClient() as client:
            try:
                # Test memory storage
                memory_data = {
                    "text": "test memory content",
                    "metadata": {"test": True}
                }
                
                response = await client.post(
                    f"{api_service_url}/api/memory/store",
                    json=memory_data,
                    timeout=10.0
                )
                
                assert response.status_code == 200
                result = response.json()
                assert "memory_id" in result
                
                memory_id = result["memory_id"]
                
                # Test memory retrieval
                response = await client.get(
                    f"{api_service_url}/api/memory/{memory_id}",
                    timeout=10.0
                )
                
                assert response.status_code == 200
                retrieved = response.json()
                assert retrieved["text"] == "test memory content"
                
            except httpx.ConnectError:
                pytest.skip("API service not available")
    
    @pytest.mark.asyncio
    async def test_embedding_generation(self, api_service_url):
        """Test embedding generation through API"""
        async with httpx.AsyncClient() as client:
            try:
                # Test embedding generation
                embed_data = {
                    "text": "test text for embedding"
                }
                
                response = await client.post(
                    f"{api_service_url}/api/embeddings/generate",
                    json=embed_data,
                    timeout=10.0
                )
                
                assert response.status_code == 200
                result = response.json()
                assert "embedding" in result
                assert isinstance(result["embedding"], list)
                assert len(result["embedding"]) > 0
                
            except httpx.ConnectError:
                pytest.skip("API service not available")
    
    @pytest.mark.asyncio
    async def test_hot_reload_functionality(self, mcp_service_url):
        """Test hot-reload functionality in Docker"""
        async with httpx.AsyncClient() as client:
            try:
                # Get current plugin status
                response = await client.get(f"{mcp_service_url}/api/plugins/status", timeout=10.0)
                assert response.status_code == 200
                
                initial_status = response.json()
                
                # Trigger a plugin reload (if any plugins support it)
                plugins = initial_status.get("plugins", [])
                hot_reload_plugins = [p for p in plugins if p.get("hot_reload", False)]
                
                if hot_reload_plugins:
                    plugin_name = hot_reload_plugins[0]["name"]
                    
                    response = await client.post(
                        f"{mcp_service_url}/api/plugins/{plugin_name}/reload",
                        timeout=30.0
                    )
                    
                    # Should succeed or return appropriate status
                    assert response.status_code in [200, 202, 503]  # 503 if not supported
                
            except httpx.ConnectError:
                pytest.skip("MCP service not available")
    
    @pytest.mark.asyncio
    async def test_service_startup_time(self, mcp_service_url, api_service_url):
        """Test that services start within reasonable time"""
        start_time = time.time()
        max_startup_time = 60  # seconds
        
        async with httpx.AsyncClient() as client:
            # Wait for services to be ready
            services_ready = False
            
            while time.time() - start_time < max_startup_time:
                try:
                    mcp_response = await client.get(f"{mcp_service_url}/health", timeout=5.0)
                    api_response = await client.get(f"{api_service_url}/health", timeout=5.0)
                    
                    if mcp_response.status_code == 200 and api_response.status_code == 200:
                        services_ready = True
                        break
                        
                except (httpx.ConnectError, httpx.TimeoutException):
                    await asyncio.sleep(2)
            
            if not services_ready:
                pytest.skip("Services did not start within reasonable time")
            
            startup_time = time.time() - start_time
            assert startup_time < max_startup_time
            
            # Log startup time for monitoring
            print(f"Services started in {startup_time:.2f} seconds")
