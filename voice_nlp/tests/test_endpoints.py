from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "voice_nlp"

def test_followup_ood(monkeypatch):
    # Exercise OOD handling with a real classifier and an offline session fixture.
    from api import endpoints
    from pipeline.classifier import load_models
    load_models()
    monkeypatch.setattr(endpoints, "get_session", lambda session_id: {
        "disease": "Brown Spot", "question_index": 0,
        "answers": [], "question_dict": {}, "confidence_trajectory": [],
    })
    monkeypatch.setattr(endpoints, "delete_session", lambda session_id: None)
    monkeypatch.setattr(endpoints, "synthesise_result", lambda **kwargs: "")
    response = client.post(
        "/followup", json={"answer": "hello", "session_id": "test-session"}
    )
    assert response.status_code == 200
    assert response.json()["is_ood"] is True
