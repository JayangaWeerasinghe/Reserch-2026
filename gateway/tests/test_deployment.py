import httpx
import pytest
from fastapi.testclient import TestClient
from main import app
from services.service_client import downstream_response, service_base_url


def test_health():
    assert TestClient(app).get("/health").json()["service"] == "gateway"


def test_service_url_override(monkeypatch):
    monkeypatch.setenv("VOICE_NLP_URL", "https://example.invalid/base///")
    assert service_base_url("VOICE_NLP_URL", "http://voice_nlp:8001", "http://localhost:8001") == "https://example.invalid/base"


@pytest.mark.parametrize("status,body", [(200, b'{"ok":true}'), (422, b'{"detail":"bad input"}'), (503, b'upstream unavailable'), (204, b'')])
def test_downstream_status_and_non_json(status, body):
    response = downstream_response(httpx.Response(status, content=body))
    assert response.status_code == status
    if status == 204:
        assert response.body == b''
    elif body == b'upstream unavailable':
        assert b'upstream unavailable' in response.body


@pytest.mark.parametrize("error,status", [(httpx.ConnectError("unreachable"), 503), (httpx.ConnectTimeout("timed out"), 504), (httpx.ReadTimeout("timed out"), 504)])
def test_proxy_failure_status(monkeypatch, error, status):
    from router import chat
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            raise error
    monkeypatch.setattr(chat.httpx, "AsyncClient", Client)
    # Client mock applies to route execution; TestClient uses sync httpx.Client.
    assert TestClient(app).post("/api/v1/chat/message", json={}).status_code == status
