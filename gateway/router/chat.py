"""Routes chatbot requests to C4 treatment_advisory_chatbot service."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from services.service_client import downstream_response, service_base_url
import httpx, os

router = APIRouter()
TREATMENT_CHATBOT_URL = service_base_url("TREATMENT_CHATBOT_URL", "http://treatment_advisory_chatbot:8004", "http://localhost:8004")

@router.post("/message")
async def send_message(payload: dict):
    """Forward chat message to C4 RAG chatbot."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{TREATMENT_CHATBOT_URL}/chat", json=payload)
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Treatment chatbot service unavailable")


@router.get("/topics")
async def list_topics():
    """Forward to C4's GET /chat/topics — the scoped disease/pest list the frontend renders as suggestion chips."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{TREATMENT_CHATBOT_URL}/chat/topics")
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Treatment chatbot service unavailable")


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Forward to C4's DELETE /chat/session/:sessionId — used when the user starts a new chat."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{TREATMENT_CHATBOT_URL}/chat/session/{session_id}")
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Treatment chatbot service unavailable")
