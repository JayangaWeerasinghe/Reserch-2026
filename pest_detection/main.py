"""PaddyGuard AI — C3 Rice Pest Detection Service.

Research-facing project structure with the original working DenseNet121
backend preserved underneath `pipeline/`.
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.endpoints import router, predict
from pipeline.core.config import get_settings
from pipeline.core.logging_config import configure_logging
from pipeline.detector import load_model

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lazy model loading is preserved from the working backend. This avoids
    # importing/loading the 28 MB DenseNet checkpoint during module import.
    yield


app = FastAPI(
    title="PaddyGuard AI — Pest Detection",
    description=(
        "C3: DenseNet121 rice pest detection with image-quality awareness, "
        "Mahalanobis OOD detection, Grad-CAM explainability, and selective "
        "few-shot new-pest adaptation."
    ),
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Original frontend contract.
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "PaddyGuard AI Pest Detection service is running",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/health")
def root_health():
    service = load_model()
    return {
        "status": "ok",
        "service": "pest_detection",
        "component": "C3",
        "model_loaded": service.classifier.model is not None,
        "device": str(service.classifier.device),
        "model_name": "DenseNet121",
    }


# Research scaffold compatibility: /detect is available in addition to the
# existing /api/v1/predict route used by the React frontend.
from schemas.request_schema import PredictionResponse

app.add_api_route(
    "/detect",
    predict,
    methods=["POST"],
    response_model=PredictionResponse,
    include_in_schema=True,
    tags=["research"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("SERVICE_PORT", "8000")),
        reload=True,
    )
