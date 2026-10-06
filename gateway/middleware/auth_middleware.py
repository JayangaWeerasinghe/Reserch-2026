"""JWT validation middleware."""
from fastapi import Request, HTTPException
from jose import JWTError, jwt
import os

JWT_SECRET    = os.getenv("JWT_SECRET", "dev_secret")
JWT_ALGORITHM = "HS256"

PUBLIC_ROUTES = ["/health", "/", "/api/v1/auth/login", "/api/v1/auth/register"]

async def verify_token(request: Request, call_next):
    if request.url.path in PUBLIC_ROUTES:
        return await call_next(request)
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return await call_next(request)
