"""Routes pest image requests to C3 pest_detection service."""
from fastapi import Request, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from services.service_client import downstream_response, service_base_url
from services.activity import observe
import httpx, os

router = APIRouter()
PEST_DETECTION_URL = service_base_url("PEST_DETECTION_URL", "http://pest_detection:8003", "http://localhost:8003")


@router.post("/detect")
async def detect_pest(request: Request, image: UploadFile = File(None), file: UploadFile = File(None)):
    if (image is None) == (file is None):
        raise HTTPException(422, "Supply exactly one image or file field")
    image = image or file
    """Forward pest image to C3 for pest identification.

    C3's real endpoint is POST /detect with the image sent under the
    form field name "file" (see pest_detection/api/endpoints.py::predict).
    """
    try:
        content = await image.read()
        files = {"file": (image.filename, content, image.content_type)}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{PEST_DETECTION_URL}/detect", files=files)
        await observe(request, response, "PEST_DIAGNOSIS_COMPLETED")
        try:
            data = response.json()
        except ValueError:
            data = {"detail": response.text}
        return JSONResponse(status_code=response.status_code, content=data)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Downstream service timed out")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Pest detection service unavailable")
