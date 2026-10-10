"""Database-authoritative authentication and role dependencies."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from models.user import User, get_db
from services.jwt_service import verify_token


def get_current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = verify_token(token)
        user = db.get(User, payload.get("sub")) if isinstance(payload.get("sub"), str) else None
    except ValueError:
        user = None
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid or inactive account", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_system_admin(user: User = Depends(get_current_user)):
    if user.role != "SYSTEM_ADMIN":
        raise HTTPException(403, "System Admin role required")
    return user
