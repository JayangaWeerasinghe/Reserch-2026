from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "voice_nlp"

def test_followup_ood():
    response = client.post(
        "/followup", json={"answer": "hello", "session_id": "test-session"}
    )
    assert response.status_code == 200
    assert response.json()["is_ood"] is True
