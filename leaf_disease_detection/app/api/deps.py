from functools import wraps

from flask import g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..config import settings
from app.repositories.expert_repository import ExpertRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.user_repository import UserRepository

serializer = URLSafeTimedSerializer(settings.secret_key)


def verify_token_details(token):
    if not token:
        return None, "Token is missing", 401
    try:
        data = serializer.loads(
            token,
            salt="auth-token",
            max_age=settings.auth_token_max_age_seconds
        )
    except SignatureExpired:
        return None, "Token has expired", 401
    except BadSignature:
        return None, "Token is invalid", 401

    username = data.get("username")
    role = data.get("role")
    user_id = data.get("user_id")

    if role == "EXPERT":
        user = ExpertRepository().find_by_username(username)
        if not user or not user.is_active:
            return None, "User account is disabled or does not exist", 403
    elif role == "SUPER_ADMIN":
        if username != settings.super_admin_username:
            return None, "Token is invalid", 401
    elif role == "USER":
        user = UserRepository().find_by_id(user_id)
        if not user or not user.is_active:
            return None, "User account is disabled or does not exist", 403
    else:
        return None, "Invalid role", 401

    return {"username": username, "role": role, "user_id": user_id}, None, None


def token_required(required_role=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            if "Authorization" in request.headers:
                auth_header = request.headers["Authorization"]
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]

            user_info, err_msg, status_code = verify_token_details(token)
            if err_msg:
                return jsonify({"detail": err_msg}), status_code

            role = user_info["role"]
            if required_role == "SUPER_ADMIN" and role != "SUPER_ADMIN":
                return jsonify({"detail": "Access forbidden: Super Admin role required"}), 403

            if required_role == "EXPERT" and role not in ["EXPERT", "SUPER_ADMIN"]:
                return jsonify({"detail": "Access forbidden: Expert or Super Admin role required"}), 403

            if required_role == "USER" and role not in ["USER", "EXPERT", "SUPER_ADMIN"]:
                return jsonify({"detail": "Access forbidden: User role required"}), 403

            g.current_user = user_info
            return f(*args, **kwargs)
        return decorated
    return decorator


def get_top_k_candidates():
    repo = PredictionRepository()
    return repo.find_top_k_candidates(limit=5)
