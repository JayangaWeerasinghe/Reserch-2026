import logging
import os
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from PIL import Image

from .deps import token_required
from ..config import settings
from ..ml_service import model_service
from training import model_retention

logger = logging.getLogger(__name__)

finetune_bp = Blueprint("finetune", __name__)


def _stream_training_subprocess(process, log_file_path, job_id):
    """Tee the fine-tuning subprocess output to the backend console and to its log file.

    Runs in a daemon thread so the request handler is never blocked on training I/O.
    """
    try:
        with open(log_file_path, "w") as log_file:
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break
                sys.stdout.write(line)
                sys.stdout.flush()
                log_file.write(line)
                log_file.flush()
    except Exception as exc:
        logger.error(f"[FINE-TUNE] Error streaming training output for job {job_id}: {exc}", exc_info=True)
    finally:
        process.stdout.close()
        process.wait()


@finetune_bp.route("/api/expert/fine-tune/readiness", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def check_fine_tune_readiness():
    try:
        eligible_samples = g.prediction_repo.count_eligible_fine_tune_samples()
        min_required = settings.min_fine_tune_samples
        sufficient_samples = eligible_samples >= min_required

        # Test dataset check
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_dir = os.path.join(backend_dir, settings.test_dataset_path)
        test_dataset_ready = False
        class_counts = {}

        if os.path.exists(test_dir) and os.path.isdir(test_dir):
            classes = ["Bacterial_Blight", "Brown_Spot", "Healthy", "Leaf_Blast"]
            has_all_classes = True
            for c in classes:
                c_dir = os.path.join(test_dir, c)
                if os.path.exists(c_dir) and os.path.isdir(c_dir):
                    count = len([f for f in os.listdir(c_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                    class_counts[c] = count
                    if count == 0:
                        has_all_classes = False
                else:
                    has_all_classes = False

            if has_all_classes:
                test_dataset_ready = True

        blockers = []
        if not sufficient_samples:
            blockers.append(f"Insufficient samples ({eligible_samples}/{min_required})")
        if not test_dataset_ready:
            blockers.append("Test dataset missing or incomplete")

        return jsonify({
            "eligible_new_samples": eligible_samples,
            "min_required": min_required,
            "sufficient_samples": sufficient_samples,
            "test_dataset_ready": test_dataset_ready,
            "test_dataset_path": test_dir,
            "test_dataset_class_counts": class_counts,
            "can_train": sufficient_samples and test_dataset_ready,
            "blockers": blockers
        })
    except Exception as exc:
        logger.error(f"Error checking readiness: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@finetune_bp.route("/api/expert/fine-tune/start", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def start_fine_tuning():
    try:
        # 1. Re-check readiness
        eligible_samples = g.prediction_repo.find_eligible_fine_tune_samples()
        if len(eligible_samples) < settings.min_fine_tune_samples:
            return jsonify({"detail": f"Insufficient samples ({len(eligible_samples)}/{settings.min_fine_tune_samples})"}), 400

        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        test_dir = os.path.join(backend_dir, settings.test_dataset_path)
        if not os.path.exists(test_dir):
            return jsonify({"detail": "Test dataset not available"}), 400

        # 2. Get active model
        active_record = g.deployment_repo.find_active()
        base_checkpoint = active_record.checkpoint_path if active_record else settings.model_path

        if not os.path.isabs(base_checkpoint):
            base_checkpoint = os.path.join(backend_dir, base_checkpoint)

        if not os.path.exists(base_checkpoint):
            # The active deployment record can point at a checkpoint path from a
            # different machine (model files aren't synced between dev machines
            # even though the deployment DB is shared). Fall back to the local
            # default model so fine-tuning can still proceed.
            fallback_checkpoint = settings.model_path
            if not os.path.isabs(fallback_checkpoint):
                fallback_checkpoint = os.path.join(backend_dir, fallback_checkpoint)
            if os.path.exists(fallback_checkpoint):
                logger.warning(
                    f"[FINE-TUNE] Active checkpoint {base_checkpoint} not found locally; "
                    f"falling back to {fallback_checkpoint}"
                )
                base_checkpoint = fallback_checkpoint

        if not os.path.exists(base_checkpoint):
            return jsonify({"detail": f"Base model checkpoint not found at {base_checkpoint}"}), 400

        # 3. Create job
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        job_id = f"FT-{timestamp}-{uuid.uuid4().hex[:6].upper()}"

        job_data = {
            "job_id": job_id,
            "status": "QUEUED",
            "source_sample_count": len(eligible_samples),
            "base_checkpoint": base_checkpoint,
            "total_epochs": settings.fine_tune_epochs
        }
        g.training_repo.create(job_data)

        # Consume samples
        for s in eligible_samples:
            g.prediction_repo.update(s.case_id, {"consumed_by_job_id": job_id})

        # Stats for [DATA] console logging only (does not affect sample selection)
        total_verified_samples = g.prediction_repo.count_verified_expert_samples()
        ood_excluded_samples = g.prediction_repo.count_ood_excluded_unconsumed_samples()

        # 4. Launch subprocess
        trainer_script = os.path.join(backend_dir, "training", "active_learning_trainer.py")
        mongodb_uri_arg = settings.mongodb_uri or "mongodb://localhost:27017"

        cmd = [
            sys.executable,
            trainer_script,
            "--job-id", job_id,
            "--mongodb-uri", mongodb_uri_arg,
            "--test-dir", test_dir,
            "--base-model", base_checkpoint,
            "--epochs", str(settings.fine_tune_epochs),
            "--total-verified-samples", str(total_verified_samples),
            "--ood-excluded-samples", str(ood_excluded_samples)
        ]

        log_file = os.path.join(backend_dir, "data", "training_logs", f"{job_id}.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logger.info(f"[FINE-TUNE] Job {job_id} queued - launching real PyTorch trainer subprocess")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=backend_dir,
            bufsize=1,
            universal_newlines=True
        )
        threading.Thread(
            target=_stream_training_subprocess,
            args=(process, log_file, job_id),
            daemon=True
        ).start()

        return jsonify({"job_id": job_id, "message": "Training job launched"}), 201

    except Exception as exc:
        logger.error(f"Error starting training: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@finetune_bp.route("/api/expert/fine-tune/status/<job_id>", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def get_job_status(job_id):
    try:
        job = g.training_repo.find_by_job_id(job_id)
        if not job:
            return jsonify({"detail": "Job not found"}), 404

        return jsonify({
            "job_id": job.job_id,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "epochs_completed": job.epochs_completed,
            "total_epochs": job.total_epochs,
            "log_tail": job.log_tail,
            "decision": job.decision,
            "candidate_accuracy": job.candidate_accuracy,
            "candidate_macro_f1": job.candidate_macro_f1,
            "accuracy_delta": job.accuracy_delta,
            "f1_delta": job.f1_delta,
            "error_message": job.error_message
        })
    except Exception as exc:
        logger.error(f"Error getting job status: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@finetune_bp.route("/api/expert/fine-tune/jobs", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def list_jobs():
    try:
        jobs = g.training_repo.list_all()
        result = []
        for j in jobs:
            result.append({
                "job_id": j.job_id,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "source_sample_count": j.source_sample_count,
                "decision": j.decision,
                "candidate_accuracy": j.candidate_accuracy,
                "candidate_macro_f1": j.candidate_macro_f1,
                "accuracy_delta": j.accuracy_delta,
                "f1_delta": j.f1_delta
            })
        return jsonify(result)
    except Exception as exc:
        logger.error(f"Error listing jobs: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@finetune_bp.route("/api/expert/deployed-model", methods=["GET"])
def get_deployed_model():
    try:
        record = g.deployment_repo.find_active()
        if record:
            return jsonify({
                "checkpoint": os.path.basename(record.checkpoint_path),
                "test_accuracy": record.test_accuracy,
                "macro_f1": record.macro_f1,
                "deployed_at": record.deployed_at.isoformat() if record.deployed_at else None,
                "notes": record.notes
            })
        else:
            return jsonify({
                "checkpoint": "PaddyGuard_active_learning_round2.pth",
                "test_accuracy": 0.9714,
                "macro_f1": 0.9714,
                "deployed_at": None,
                "notes": "Static baseline"
            })
    except Exception as exc:
        logger.error(f"Error getting deployed model: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@finetune_bp.route("/api/expert/fine-tune/<job_id>/promote", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def promote_candidate(job_id):
    try:
        job = g.training_repo.find_by_job_id(job_id)
        if not job:
            return jsonify({"detail": "Job not found"}), 404

        if job.status != "COMPLETED" or job.decision != "ELIGIBLE_FOR_PROMOTION":
            return jsonify({"detail": "Job is not eligible for promotion"}), 400

        # 1. Update backend paths
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        models_dir = os.path.join(backend_dir, "models")
        active_model_path = os.path.join(models_dir, "active_model.pth")

        # 2. Backup current active model on disk
        current_record = g.deployment_repo.find_active()
        current_checkpoint_abs = None
        if current_record and current_record.checkpoint_path:
            current_checkpoint_abs = current_record.checkpoint_path
            if not os.path.isabs(current_checkpoint_abs):
                current_checkpoint_abs = os.path.join(backend_dir, current_checkpoint_abs)
        if current_checkpoint_abs and os.path.exists(current_checkpoint_abs):
            backup_dir = os.path.join(models_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}_{os.path.basename(current_checkpoint_abs)}"
            shutil.copy2(current_checkpoint_abs, os.path.join(backup_dir, backup_name))

        # 3. Copy candidate checkpoint to active_model.pth
        shutil.copy2(job.candidate_checkpoint, active_model_path)

        # 4. Update .env MODEL_PATH (if .env is writable)
        try:
            env_path = os.path.join(backend_dir, ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                with open(env_path, 'w') as f:
                    for line in lines:
                        if line.startswith("MODEL_PATH="):
                            f.write("MODEL_PATH=models/active_model.pth\n")
                        else:
                            f.write(line)
        except Exception as e:
            logger.warning(f"Could not update .env MODEL_PATH: {e}")

        settings.model_path = "models/active_model.pth"

        # 5. Hot reload the model service
        try:
            model_service.reload()
            # Try a sanity prediction (blank image)
            img = Image.new('RGB', (300, 300), color='white')
            model_service.predict(img)
        except Exception as e:
            # Revert model reload
            if current_record:
                settings.model_path = current_record.checkpoint_path
                model_service.reload()
            return jsonify({"detail": f"Model reload failed: {e}. Reverted to previous model."}), 500

        # 6. Update deployment history records in MongoDB
        g.deployment_repo.deactivate_all()

        new_record = {
            "checkpoint_path": os.path.relpath(active_model_path, backend_dir),
            "test_accuracy": job.candidate_accuracy,
            "macro_f1": job.candidate_macro_f1,
            "deployed_by": g.current_user["username"],
            "notes": f"Promoted from job {job_id}",
            "is_active": True
        }
        g.deployment_repo.create(new_record)

        # Mark job as promoted
        g.training_repo.update(job_id, {"decision": "PROMOTED", "status": "PROMOTED"})

        try:
            model_retention.run_model_retention_cleanup()
        except Exception as e:
            logger.error(f"Failed to run model retention after promote: {e}", exc_info=True)

        return jsonify({"message": "Model promoted successfully"})

    except Exception as exc:
        logger.error(f"Error promoting model: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
