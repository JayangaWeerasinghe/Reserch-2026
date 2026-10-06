# voice_nlp/pipeline/db.py
# leaf_disease_detection/pipeline/db.py   ← same file, paste in each service
# pest_detection/pipeline/db.py
"""
MongoDB logging for this service.
Each service has its own copy — microservice independence.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os, logging

logger  = logging.getLogger(__name__)
_client = None

def _get_db():
    global _client
    url = os.getenv("MONGO_URL", "").strip()
    if not url:
        return None
    if _client is None:
        _client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, socketTimeoutMS=2000)
        logger.info("MongoDB connected")
    return _client["paddyguard"]

async def log_diagnosis(payload: dict) -> None:
    """Insert one diagnosis log record. Never raises — logging must not break pipeline."""
    try:
        db = _get_db()
        if db is None:
            return
        await db.diagnoses.insert_one({
            **payload,
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error("MongoDB log failed (non-fatal): %s", type(e).__name__)