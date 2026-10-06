"""Routes auth requests to user_management service."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from services.service_client import downstream_response
import httpx, os

router = APIRouter()

def _default_service_url(container_url: str, local_url: str) -> str:
    override = os.getenv("USER_MGMT_URL")
    if override:
        return override.rstrip("/")
    if os.path.exists("/.dockerenv"):
        return container_url
    return local_url


USER_MGMT_URL = _default_service_url("http://user_management:8005", "http://localhost:8005")


async def _forward(request: Request, method: str, path: str, json=None):
    headers = {}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, f"{USER_MGMT_URL}{path}", headers=headers, json=json)
        try:
            content = response.json()
        except ValueError:
            content = {"detail": response.text}
        return JSONResponse(status_code=response.status_code, content=content)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="User management service unavailable")


@router.post("/register")
async def register(payload: dict):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{USER_MGMT_URL}/register", json=payload)
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="User management service unavailable")


@router.post("/login")
async def login(payload: dict):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{USER_MGMT_URL}/login", json=payload)
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="User management service unavailable")


@router.post("/refresh")
async def refresh(payload: dict):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{USER_MGMT_URL}/refresh", json=payload)
            return downstream_response(response)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="User management service unavailable")


@router.get("/me")
async def me(request: Request):
    return await _forward(request, "GET", "/me")


@router.patch("/me")
async def update_me(request: Request):
    body = await request.json()
    return await _forward(request, "PATCH", "/me", json=body)
