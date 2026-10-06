"""
PaddyGuard AI — C1 Voice NLP Service
Owner: Jayonga Weerasinghe (IT22273680)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging, os

load_dotenv()
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger("voice_nlp")

from api.endpoints import router
from pipeline.classifier import load_models
from pipeline.asr import preload_asr


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("  PaddyGuard AI — C1 Voice NLP Service starting")
    logger.info("=" * 50)
    logger.info("Loading SVM classifier and TF-IDF vectoriser...")
    for variable, default in (("MODEL_PATH", "models/paddyguard_best_classifier.pkl"),
                              ("TFIDF_PATH", "models/paddyguard_tfidf.pkl")):
        if not os.path.isfile(os.getenv(variable, default)):
            logger.error("Required classifier artifact missing: %s; classification cannot work", variable)
    try:
        load_models()
        logger.info("Loading ASR (Whisper) model eagerly; healthcheck waits for completion...")
        preload_asr()
    except Exception:
        logger.error("Model startup failed; verify trained artifacts, Hugging Face access and available RAM")
        raise
    logger.info("All models loaded — ready to serve on port %s",
                os.getenv("PORT", os.getenv("SERVICE_PORT", "8001")))
    yield
    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Voice NLP Service shutting down")


app = FastAPI(
    title       = "PaddyGuard AI — Voice NLP Service",
    description = "C1: Sinhala voice to rice disease classification",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if origin.strip()],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {
        "status"   : "ok",
        "service"  : "voice_nlp",
        "component": "C1",
        "version"  : "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host      = "0.0.0.0",
        port      = int(os.getenv("PORT", os.getenv("PORT", os.getenv("SERVICE_PORT", "8001")))),
        reload    = False,
        log_level = "info",
    )