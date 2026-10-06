import csv
import io
import json
import logging
import os
import uuid
import zipfile
from datetime import datetime

import requests
from flask import Blueprint, current_app, g, jsonify, send_file

from .deps import token_required

logger = logging.getLogger(__name__)

active_learning_bp = Blueprint("active_learning", __name__)


@active_learning_bp.route("/api/expert/active-learning/prepare-batch", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def prepare_batch():
    try:
        exclude_case_ids = g.active_learning_repo.get_all_batch_sample_case_ids()
        eligible_cases = g.prediction_repo.find_verified_unused_samples(exclude_case_ids)

        sample_count = len(eligible_cases)
        if sample_count == 0:
            return jsonify({"detail": "No eligible samples available for a new batch."}), 400

        batch_id = f"AL-BATCH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        is_demo_mode = sample_count < 100

        new_batch = {
            "batch_id": batch_id,
            "sample_count": sample_count,
            "status": "READY",
            "is_demo_mode": is_demo_mode,
            "recommended_batch_size": 100
        }
        g.active_learning_repo.create_batch(new_batch)

        for case in eligible_cases:
            g.active_learning_repo.add_batch_sample(batch_id, case.case_id)

        return jsonify({
            "batch_id": batch_id,
            "sample_count": sample_count,
            "recommended_batch_size": 100,
            "is_demo_mode": is_demo_mode,
            "status": "READY"
        })
    except Exception as exc:
        logger.error(f"Error preparing batch: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@active_learning_bp.route("/api/expert/active-learning/batches", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def list_batches():
    try:
        batches = g.active_learning_repo.list_all_batches()
        result = []
        for b in batches:
            result.append({
                "batch_id": b.batch_id,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "sample_count": b.sample_count,
                "status": b.status,
                "is_demo_mode": b.is_demo_mode,
                "recommended_batch_size": b.recommended_batch_size
            })
        return jsonify(result)
    except Exception as exc:
        logger.error(f"Error listing batches: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@active_learning_bp.route("/api/expert/active-learning/batches/<batch_id>", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def get_batch(batch_id):
    try:
        batch = g.active_learning_repo.find_batch_by_id(batch_id)
        if not batch:
            return jsonify({"detail": "Batch not found"}), 404

        samples = g.active_learning_repo.find_samples_by_batch_id(batch_id)

        samples_list = []
        for s in samples:
            samples_list.append({
                "case_id": s.case_id,
                "predicted_disease": s.predicted_disease,
                "confidence": s.confidence,
                "expert_validated_disease": s.expert_validated_disease,
                "review_reason": s.review_reason
            })

        return jsonify({
            "batch": {
                "batch_id": batch.batch_id,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "sample_count": batch.sample_count,
                "status": batch.status,
                "is_demo_mode": batch.is_demo_mode,
                "recommended_batch_size": batch.recommended_batch_size
            },
            "samples": samples_list
        })
    except Exception as exc:
        logger.error(f"Error getting batch {batch_id}: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@active_learning_bp.route("/api/expert/active-learning/batches/<batch_id>/start", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def start_batch_retraining(batch_id):
    try:
        batch = g.active_learning_repo.find_batch_by_id(batch_id)
        if not batch:
            return jsonify({"detail": "Batch not found"}), 404

        if batch.status != "READY":
            return jsonify({"detail": "Batch is already started or completed"}), 400

        status = "TRAINING_SIMULATION" if batch.is_demo_mode else "TRAINING"
        g.active_learning_repo.update_batch(batch_id, {"status": status})

        return jsonify({"message": "Retraining started", "status": status})
    except Exception as exc:
        logger.error(f"Error starting batch {batch_id}: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@active_learning_bp.route("/api/expert/active-learning/batches/<batch_id>", methods=["DELETE"])
@token_required(required_role="SUPER_ADMIN")
def delete_batch(batch_id):
    try:
        batch = g.active_learning_repo.find_batch_by_id(batch_id)
        if not batch:
            return jsonify({"detail": "Batch not found"}), 404

        if batch.status in ["TRAINING", "TRAINING_SIMULATION"]:
            return jsonify({"detail": "Cannot delete this batch because it is being used by a training job."}), 409

        if hasattr(g, 'training_repo'):
            related_jobs = g.training_repo.list_all()
            for job in related_jobs:
                if getattr(job, 'batch_id', None) == batch_id or getattr(job, 'source_batch_id', None) == batch_id:
                    return jsonify({"detail": "Cannot delete this batch because it is referenced by an active job."}), 409

        g.active_learning_repo.sample_collection.delete_many({"batch_id": batch_id})
        g.active_learning_repo.batch_collection.delete_one({"batch_id": batch_id})
        return jsonify({"message": "Batch deleted successfully."})
    except Exception as exc:
        logger.error(f"Error deleting batch {batch_id}: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@active_learning_bp.route("/api/expert/active-learning/batches/<batch_id>/export", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def export_batch(batch_id):
    try:
        batch = g.active_learning_repo.find_batch_by_id(batch_id)
        if not batch:
            return jsonify({"detail": "Batch not found"}), 404

        samples = g.active_learning_repo.find_samples_by_batch_id(batch_id)

        # 1. Create Manifest and collect trainable info
        manifest_data = []
        trainable_sample_count = 0
        temp_downloaded_paths = []

        for s in samples:
            # Check validation rules
            if s.review_status != "verified" or not s.approved_for_training or not s.expert_validated_disease:
                continue

            if s.expert_validated_disease not in ["Bacterial_Blight", "Brown_Spot", "Healthy", "Leaf_Blast"]:
                continue

            original_image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], s.image_name) if s.image_name else None
            image_exists = original_image_path and os.path.exists(original_image_path)

            # If the image is not local, temporarily download it from Cloudinary
            if not image_exists and s.image_url:
                try:
                    logger.info(f"Downloading original image for zip export from Cloudinary: {s.image_url}")
                    r_img = requests.get(s.image_url, timeout=10)
                    if r_img.status_code == 200:
                        os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
                        with open(original_image_path, "wb") as f_img:
                            f_img.write(r_img.content)
                        image_exists = True
                        temp_downloaded_paths.append(original_image_path)
                except Exception as e:
                    logger.error(f"Failed to download image from Cloudinary for zip: {e}")

            manifest_data.append({
                "case_id": s.case_id,
                "image_filename": s.image_name if s.image_name else "",
                "image_available": str(image_exists).lower(),
                "ai_prediction": s.predicted_disease,
                "ai_confidence": s.confidence,
                "expert_label": s.expert_validated_disease,
                "review_reason": s.review_reason,
                "review_status": s.review_status,
                "verified_at": s.verified_at.isoformat() if s.verified_at else ""
            })
            if image_exists:
                trainable_sample_count += 1

        # 2. Update tracking
        g.active_learning_repo.update_batch(batch_id, {
            "exported_at": datetime.utcnow(),
            "export_count": batch.export_count + 1
        })

        # 3. Create Metadata
        metadata = {
            "project": "PaddyGuard AI",
            "batch_id": batch.batch_id,
            "source": getattr(batch, "source", "EXPERT_VERIFIED_ACTIVE_LEARNING"),
            "created_at": batch.created_at.isoformat() if batch.created_at else "",
            "exported_at": datetime.utcnow().isoformat(),
            "sample_count": batch.sample_count,
            "trainable_sample_count": trainable_sample_count,
            "recommended_batch_size": batch.recommended_batch_size,
            "is_demo_mode": batch.is_demo_mode,
            "deployed_model": "PaddyGuard_active_learning_round2.pth",
            "deployed_model_test_accuracy": 0.9714,
            "deployed_model_macro_f1": 0.9714,
            "architecture": "EfficientNetB3",
            "classes": [
                "Bacterial_Blight",
                "Brown_Spot",
                "Healthy",
                "Leaf_Blast"
            ],
            "purpose": "Controlled offline Active Learning retraining"
        }

        # 4. Generate ZIP in memory
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"PaddyGuard_AL_BATCH_{batch_id}/batch_metadata.json", json.dumps(metadata, indent=2))

            if manifest_data:
                manifest_io = io.StringIO()
                fieldnames = ["case_id", "image_filename", "image_available", "ai_prediction", "ai_confidence", "expert_label", "review_reason", "review_status", "verified_at"]
                writer = csv.DictWriter(manifest_io, fieldnames=fieldnames)
                writer.writeheader()
                for row in manifest_data:
                    writer.writerow(row)
                zf.writestr(f"PaddyGuard_AL_BATCH_{batch_id}/manifest.csv", manifest_io.getvalue())

            for s in manifest_data:
                if s["image_available"] == "true":
                    img_path = os.path.join(current_app.config["UPLOAD_FOLDER"], s["image_filename"])
                    if os.path.exists(img_path):
                        zf.write(img_path, arcname=f"PaddyGuard_AL_BATCH_{batch_id}/images/{s['case_id']}{os.path.splitext(s['image_filename'])[1]}")

        memory_file.seek(0)

        # Clean up temporarily downloaded images
        for path in temp_downloaded_paths:
            try:
                os.remove(path)
            except Exception:
                pass

        return send_file(
            memory_file,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"PaddyGuard_AL_BATCH_{batch_id}.zip"
        )
    except Exception as exc:
        logger.error(f"Error exporting batch {batch_id}: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
