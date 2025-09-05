
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_echo_core_fastapi_app_creation_and_endpoints(async_test_client):
    """Test Echo Core FastAPI application creation and all endpoints"""
    # Test root endpoint
    response = await async_test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Echo Core"
    assert data["version"] == "1.0.0"
    assert data["status"] == "active"
    assert "timestamp" in data
    
    # Test health check endpoint
    response = await async_test_client.get("/health")
    assert response.status_code == 200
    health_data = response.json()
    assert health_data["status"] == "healthy"
    assert health_data["service"] == "echo-core"
    assert "timestamp" in health_data
    assert "mode" in health_data
    assert "learning_enabled" in health_data
    assert "persistence_enabled" in health_data
    
    # Test status endpoint
    response = await async_test_client.get("/status")
    assert response.status_code == 200
    status_data = response.json()
    assert "echo_core" in status_data
    assert "learning" in status_data
    assert "platform" in status_data
    assert "timestamp" in status_data
    assert status_data["echo_core"]["status"] == "active"
    assert isinstance(status_data["learning"]["enabled"], bool)
    assert isinstance(status_data["platform"]["never_terminate"], bool)
    
    # Test learn endpoint
    learn_payload = {"type": "test_data", "content": "test learning content"}
    response = await async_test_client.post("/learn", json=learn_payload)
    assert response.status_code == 200
    learn_data = response.json()
    assert learn_data["status"] == "learning"
    assert learn_data["data_type"] == "test_data"
    assert "timestamp" in learn_data
    
    # Test platform status endpoint
    response = await async_test_client.get("/platform/status")
    assert response.status_code == 200
    platform_data = response.json()
    assert "platform" in platform_data
    assert platform_data["platform"]["name"] == "AlsaniaMCP"
    assert platform_data["platform"]["echo_core"] == "active"
    assert "timestamp" in platform_data
