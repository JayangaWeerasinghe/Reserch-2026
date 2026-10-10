"""Routes voice requests to C1 voice_nlp service."""
from fastapi import Request, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from services.service_client import downstream_response, service_base_url
from services.activity import observe
import httpx, os

router = APIRouter()
VOICE_NLP_URL = service_base_url("VOICE_NLP_URL", "http://voice_nlp:8001", "http://localhost:8001")

@router.post("/diagnose")
async def diagnose_voice(request: Request, audio: UploadFile = File(...)):
    """Forward audio file to C1 voice_nlp service for diagnosis.

    Timeout is generous: the first Whisper ASR call after a cold start can
    take several minutes before the model is warm.
    """
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            files = {"audio": (audio.filename, await audio.read(), audio.content_type)}
            response = await client.post(f"{VOICE_NLP_URL}/diagnose", files=files)
            await observe(request, response, "VOICE_DIAGNOSIS_COMPLETED")
            return downstream_response(response)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Voice NLP service unavailable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Voice NLP service timed out")

@router.post("/followup")
async def followup(request: Request, payload: dict):
    """Forward follow-up answer to C1 for continued diagnosis."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{VOICE_NLP_URL}/followup", json=payload)
            await observe(request, response, "VOICE_FOLLOWUP_COMPLETED")
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Voice NLP service unavailable")
