"""
API Gateway — Rate Limiter
Uses slowapi backed by Redis so limits are shared across
all gateway worker processes (not per-process in memory).

Limits applied:
  /api/v1/voice/*   → 10 requests / minute  (Whisper is expensive)
  /api/v1/image/*   → 20 requests / minute
  /api/v1/pest/*    → 20 requests / minute
  /api/v1/chat/*    → 30 requests / minute
  /api/v1/auth/*    → 5  requests / minute  (brute force protection)
  global fallback   → 60 requests / minute  per IP
"""

import os
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger("gateway.rate_limiter")

# ── Redis-backed limiter ───────────────────────────────────────────────────
# Falls back to in-memory if Redis is not available (dev mode)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

try:
    limiter = Limiter(
        key_func        = get_remote_address,
        storage_uri     = _REDIS_URL,
        default_limits  = ["60/minute"],    # global fallback for any undecorated route
    )
    logger.info("Rate limiter using configured Redis storage")

except Exception as e:
    # Redis not available — fall back to in-memory (local dev only)
    logger.warning(
        "Redis storage initialization failed (%s). Rate limiter using in-memory storage. "
        "Do NOT use this in production.", type(e).__name__
    )
    limiter = Limiter(
        key_func       = get_remote_address,
        default_limits = ["60/minute"],
    )


# ── Per-route limit strings (import these in each router file) ─────────────

VOICE_LIMIT  = "10/minute"    # Whisper ASR is GPU-heavy — keep low
IMAGE_LIMIT  = "20/minute"    # CNN inference
PEST_LIMIT   = "20/minute"    # YOLO inference
CHAT_LIMIT   = "30/minute"    # RAG chatbot
AUTH_LIMIT   = "5/minute"     # login / register — brute force protection


# ── Custom error handler ───────────────────────────────────────────────────

async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> Response:
    """
    Return a clean JSON error instead of slowapi's default plain-text response.
    The Retry-After header tells the client when to try again.
    """
    retry_after = getattr(exc, "retry_after", 60)
    logger.warning(
        "Rate limit exceeded: IP=%s  path=%s  limit=%s",
        get_remote_address(request),
        request.url.path,
        str(exc.detail),
    )
    return JSONResponse(
        status_code = 429,
        content     = {
            "success"     : False,
            "error"       : "Too many requests",
            "detail"      : (
                f"Rate limit exceeded. "
                f"Please wait {retry_after} seconds before trying again."
            ),
            "retry_after" : retry_after,
        },
        headers = {
            "Retry-After"              : str(retry_after),
            "X-RateLimit-Limit"        : str(exc.detail),
            "X-RateLimit-Reset"        : str(retry_after),
        },
    )