"""
Redis session store for follow-up dialogue state.
Uses Upstash Redis (TLS) via REDIS_URL environment variable.
Sessions expire automatically after 30 minutes.

Novelty 3: Confidence trajectory tracking added.
Each session now records how confidence changes across follow-up questions,
creating a diagnostic path showing the system converging on a diagnosis.
"""

import redis, json, os, logging
from uuid import uuid4

logger      = logging.getLogger("voice_nlp.session_store")
SESSION_TTL = 1800  # 30 minutes

_redis_client = None

def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = redis.Redis.from_url(
            url,
            decode_responses       = True,
            socket_timeout         = 5,
            socket_connect_timeout = 5,
        )
        try:
            _redis_client.ping()
            logger.info("[session_store] Redis connected OK")
        except Exception as e:
            logger.error("[session_store] Redis connection failed: %s", e)
    return _redis_client


def _key(session_id: str) -> str:
    return f"paddyguard:session:{session_id}"


def create_session(disease: str, confidence: float) -> str:
    """
    Create a new follow-up session. Returns session_id.
    Initialises confidence_trajectory with the initial classification result.
    """
    session_id = str(uuid4())
    data = {
        "disease"       : disease,
        "confidence"    : confidence,
        "question_index": 0,
        "answers"       : [],
        "question_dict" : {},
        # Novelty 3: confidence trajectory — records each step
        "confidence_trajectory": [
            {
                "step"      : 0,
                "label"     : "Initial",
                "disease"   : disease,
                "confidence": round(confidence, 3),
            }
        ],
    }
    try:
        _get_redis().setex(_key(session_id), SESSION_TTL, json.dumps(data))
        logger.info("[session_store] Created session %s disease=%s conf=%.3f",
                    session_id, disease, confidence)
    except Exception as e:
        logger.error("[session_store] create_session failed: %s", e)
    return session_id


def get_session(session_id: str) -> dict | None:
    """Load session. Returns None if expired or not found."""
    try:
        raw = _get_redis().get(_key(session_id))
        if raw is None:
            logger.warning("[session_store] Session not found: %s", session_id)
            return None
        return json.loads(raw)
    except Exception as e:
        logger.error("[session_store] get_session failed: %s", e)
        return None


def update_session(session_id: str, data: dict) -> None:
    """Update session data and reset TTL."""
    try:
        _get_redis().setex(_key(session_id), SESSION_TTL, json.dumps(data))
    except Exception as e:
        logger.error("[session_store] update_session failed: %s", e)


def append_trajectory(session_id: str, step: int, label: str,
                      disease: str, confidence: float) -> list:
    """
    Append a new step to the confidence trajectory.
    Returns the updated trajectory list.
    """
    session = get_session(session_id)
    if session is None:
        return []
    trajectory = session.get("confidence_trajectory", [])
    trajectory.append({
        "step"      : step,
        "label"     : label,
        "disease"   : disease,
        "confidence": round(confidence, 3),
    })
    session["confidence_trajectory"] = trajectory
    update_session(session_id, session)
    return trajectory


def delete_session(session_id: str) -> None:
    """Delete session after follow-up completes."""
    try:
        _get_redis().delete(_key(session_id))
        logger.info("[session_store] Deleted session %s", session_id)
    except Exception as e:
        logger.error("[session_store] delete_session failed: %s", e)
