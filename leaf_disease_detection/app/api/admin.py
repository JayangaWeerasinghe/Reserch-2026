import logging

from flask import Blueprint, g, jsonify, request

from .deps import token_required
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/users", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def list_admin_users():
    try:
        user_repo = UserRepository()
        users = user_repo.list_all()

        # Aggregate prediction case counts by user_id to avoid N+1 queries
        pipeline = [
            {"$match": {"user_id": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}}
        ]
        counts_cursor = g.prediction_repo.collection.aggregate(pipeline)
        user_counts = {str(item["_id"]): item["count"] for item in counts_cursor}

        result = []
        for u in users:
            analysis_count = user_counts.get(str(u.user_id), 0)
            result.append({
                "user_id": u.user_id,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                "analysis_count": analysis_count
            })
        return jsonify(result)
    except Exception as exc:
        logger.error(f"Error listing admin users: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@admin_bp.route("/api/admin/users/<user_id>", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def get_admin_user(user_id):
    try:
        user = UserRepository().find_by_id(user_id)
        if not user:
            return jsonify({"detail": "User not found"}), 404

        analysis_count = g.prediction_repo.collection.count_documents({"user_id": str(user.user_id)})

        return jsonify({
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "analysis_count": analysis_count
        })
    except Exception as exc:
        logger.error(f"Error fetching admin user: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@admin_bp.route("/api/admin/users/<user_id>", methods=["PUT"])
@token_required(required_role="SUPER_ADMIN")
def update_admin_user(user_id):
    try:
        user_repo = UserRepository()
        user = user_repo.find_by_id(user_id)
        if not user:
            return jsonify({"detail": "User not found"}), 404

        data = request.json or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        is_active = data.get("is_active")

        if not name:
            return jsonify({"detail": "Name is required"}), 400
        if not email or "@" not in email:
            return jsonify({"detail": "Valid email is required"}), 400

        # Check duplicate email
        existing = user_repo.find_by_email(email)
        if existing and existing.user_id != user.user_id:
            return jsonify({"detail": "Email already exists"}), 400

        updates = {
            "name": name,
            "email": email
        }
        if is_active is not None:
            updates["is_active"] = bool(is_active)

        updated_user = user_repo.update(user_id, updates)
        return jsonify({
            "message": "User updated successfully",
            "user": {
                "user_id": updated_user.user_id,
                "name": updated_user.name,
                "email": updated_user.email,
                "role": updated_user.role,
                "is_active": updated_user.is_active
            }
        })
    except Exception as exc:
        logger.error(f"Error updating admin user: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@admin_bp.route("/api/admin/users/<user_id>", methods=["DELETE"])
@token_required(required_role="SUPER_ADMIN")
def delete_admin_user(user_id):
    try:
        user_repo = UserRepository()
        user = user_repo.find_by_id(user_id)
        if not user:
            return jsonify({"detail": "User not found"}), 404

        # Soft delete: deactive the user
        user_repo.update(user_id, {"is_active": False})
        return jsonify({"message": "User deactivated successfully"})
    except Exception as exc:
        logger.error(f"Error deleting admin user: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
