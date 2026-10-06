from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "PaddyGuard AI" in response.json()["message"]


def test_health_route_exists():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "pest_detection"
