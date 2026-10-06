import logging

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from .deps import token_required
from ..config import settings

logger = logging.getLogger(__name__)

expert_management_bp = Blueprint("expert_management", __name__)


@expert_management_bp.route("/api/expert-management", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def list_experts():
    try:
        users = g.expert_repo.list_all()
        result = []
        for u in users:
            result.append({
                "id": u.id,
                "name": u.name,
                "username": u.username,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "created_by": u.created_by
            })
        return jsonify(result)
    except Exception as exc:
        logger.error(f"Error listing experts: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@expert_management_bp.route("/api/expert-management", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def create_expert():
    try:
        data = request.json or {}
        name = data.get("name")
        username = data.get("username")
        password = data.get("password")

        if not name or not username or not password:
            return jsonify({"detail": "Name, username, and password are required"}), 400

        if username == settings.super_admin_username or g.expert_repo.find_by_username(username):
            return jsonify({"detail": "Username already exists"}), 400

        password_hash = generate_password_hash(password)
        new_user = {
            "name": name,
            "username": username,
            "password_hash": password_hash,
            "role": "EXPERT",
            "is_active": True,
            "created_by": g.current_user["username"]
        }
        user_record = g.expert_repo.create(new_user)

        return jsonify({
            "message": "Expert created successfully",
            "expert": {
                "id": user_record.id,
                "name": user_record.name,
                "username": user_record.username,
                "role": user_record.role,
                "is_active": user_record.is_active
            }
        }), 201
    except Exception as exc:
        logger.error(f"Error creating expert: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@expert_management_bp.route("/api/expert-management/<int:expert_id>/toggle-status", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def toggle_expert_status(expert_id):
    try:
        user = g.expert_repo.find_by_id(expert_id)
        if not user:
            return jsonify({"detail": "Expert not found"}), 404

        g.expert_repo.update(expert_id, {"is_active": not user.is_active})
        user = g.expert_repo.find_by_id(expert_id)

        status_str = "enabled" if user.is_active else "disabled"
        return jsonify({
            "message": f"Expert account {status_str} successfully",
            "expert": {
                "id": user.id,
                "username": user.username,
                "is_active": user.is_active
            }
        })
    except Exception as exc:
        logger.error(f"Error toggling expert status: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
