import logging

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .deps import serializer
from ..config import settings
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
def auth_login():
    try:
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"detail": "Username/Email and password are required"}), 400

        # 1. Super admin check
        if username == settings.super_admin_username:
            if password == settings.super_admin_password:
                token = serializer.dumps({"username": username, "role": "SUPER_ADMIN", "user_id": "SUPER_ADMIN"}, salt="auth-token")
                return jsonify({
                    "token": token,
                    "username": username,
                    "role": "SUPER_ADMIN",
                    "user": {
                        "user_id": "SUPER_ADMIN",
                        "name": "Super Admin",
                        "email": "admin@paddyguard.com",
                        "role": "SUPER_ADMIN"
                    }
                })
            else:
                return jsonify({"detail": "Invalid credentials"}), 401

        # 2. Expert check
        user = g.expert_repo.find_by_username(username)
        if user:
            if not user.is_active:
                return jsonify({"detail": "This expert account has been disabled"}), 403
            if check_password_hash(user.password_hash, password):
                token = serializer.dumps({"username": username, "role": "EXPERT", "user_id": str(user.id)}, salt="auth-token")
                return jsonify({
                    "token": token,
                    "username": username,
                    "role": "EXPERT",
                    "user": {
                        "user_id": str(user.id),
                        "name": user.name,
                        "email": user.username,
                        "role": "EXPERT"
                    }
                })
            return jsonify({"detail": "Invalid credentials"}), 401

        # 3. Normal user check (by email)
        normal_user = UserRepository().find_by_email(username)
        if normal_user:
            if not normal_user.is_active:
                return jsonify({"detail": "This account has been disabled"}), 403
            if check_password_hash(normal_user.password_hash, password):
                token = serializer.dumps({
                    "username": normal_user.email,
                    "role": "USER",
                    "user_id": normal_user.user_id
                }, salt="auth-token")
                return jsonify({
                    "token": token,
                    "username": normal_user.name,
                    "role": "USER",
                    "user": {
                        "user_id": normal_user.user_id,
                        "name": normal_user.name,
                        "email": normal_user.email,
                        "role": "USER"
                    }
                })
            return jsonify({"detail": "Invalid credentials"}), 401

        return jsonify({"detail": "Invalid credentials"}), 401
    except Exception as exc:
        logger.error(f"Error logging in: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@auth_bp.route("/api/auth/register", methods=["POST"])
def auth_register():
    try:
        logger.info("REGISTER_ROUTE_REACHED")
        data = request.json or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        password = data.get("password")

        # Validations
        if not name:
            return jsonify({"detail": "Name is required"}), 400
        if not email or "@" not in email:
            return jsonify({"detail": "Valid email is required"}), 400
        if not password or len(password) < 6:
            return jsonify({"detail": "Password must be at least 6 characters long"}), 400

        user_repo = UserRepository()
        if user_repo.find_by_email(email):
            return jsonify({"detail": "Email already registered"}), 400

        password_hash = generate_password_hash(password)
        new_user = {
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role": "USER",
            "is_active": True
        }

        user_record = user_repo.create(new_user)
        return jsonify({
            "message": "User registered successfully",
            "user": {
                "user_id": user_record.user_id,
                "name": user_record.name,
                "email": user_record.email,
                "role": user_record.role
            }
        }), 201
    except ValueError as val_err:
        logger.warning(f"Registration validation error: {val_err}")
        return jsonify({"detail": str(val_err)}), 400
    except Exception as exc:
        logger.error(f"Error registering user: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
