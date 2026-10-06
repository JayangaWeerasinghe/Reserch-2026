"""Async HTTP client for inter-service communication."""
import httpx
from typing import Any

async def post_to_service(url: str, json: dict = None,
                          files: dict = None, timeout: float = 60.0) -> Any:
    async with httpx.AsyncClient(timeout=timeout) as client:
        if files:
            return await client.post(url, files=files)
        return await client.post(url, json=json)


def downstream_response(response: httpx.Response):
    """Preserve HTTP status, including downstream non-JSON and empty responses."""
    from fastapi.responses import JSONResponse, Response
    if response.status_code in (204, 304):
        return Response(status_code=response.status_code)
    try:
        content = response.json()
    except ValueError:
        content = {"detail": response.text}
    return JSONResponse(status_code=response.status_code, content=content)


def service_base_url(variable: str, container_url: str, local_url: str) -> str:
    import os
    default = container_url if os.path.exists("/.dockerenv") else local_url
    return (os.getenv(variable) or default).strip().rstrip("/")
