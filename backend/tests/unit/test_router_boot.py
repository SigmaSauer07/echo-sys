from fastapi.testclient import TestClient
from backend.mcp.router import app

def test_router_boots_and_defaults():
    client = TestClient(app)
    r = client.post("/mcp/route", json={"input":"ping"})
    assert r.status_code == 200
