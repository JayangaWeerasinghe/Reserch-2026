import os
import logging
from datetime import datetime, timedelta
from app.config import settings
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.deployment_repository import DeploymentRepository
from app.repositories.training_repository import TrainingRepository

logger = logging.getLogger(__name__)

# Helpers
def _abs_path(path):
    if not path:
        return None
    if os.path.isabs(path):
        return os.path.normpath(path)
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.normpath(os.path.join(backend_dir, path))

def _is_within(dir_path, target_path):
    dir_path = os.path.normpath(dir_path)
    target_path = os.path.normpath(target_path)
    try:
        return os.path.commonpath([dir_path]) == os.path.commonpath([dir_path, target_path])
    except Exception:
        return False

def _safe_delete_file(abs_path, allowed_dirs, protected_paths):
    # Validate resolution
    if not abs_path or not os.path.exists(abs_path):
        return False
    abs_path = os.path.normpath(abs_path)
    # Check within allowed dirs
    allowed = False
    for d in allowed_dirs:
        if _is_within(os.path.normpath(d), abs_path):
            allowed = True
            break
    if not allowed:
        logger.warning("Refusing to delete file outside allowed dirs: %s", abs_path)
        return False
    # Protect current active and other protected paths
    for p in protected_paths:
        if not p:
            continue
        p_abs = os.path.normpath(p)
        if abs_path == p_abs:
            logger.warning("Refusing to delete protected path: %s", abs_path)
            return False
    try:
        os.remove(abs_path)
        logger.info("Deleted file: %s", abs_path)
        return True
    except Exception as e:
        logger.error("Failed to delete %s: %s", abs_path, e)
        return False

# Cleanup functions

def cleanup_rejected_candidates():
    """
    Keep only newest `settings.max_rejected_candidates` rejected candidate checkpoint files.
    Marks pruned checkpoints with `checkpoint_pruned_at` while preserving DB history.
    """
    try:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        candidates_dir = os.path.join(backend_dir, "models", "candidates")
        allowed_dirs = [candidates_dir]

        candidate_repo = CandidateRepository()
        deployment_repo = DeploymentRepository()
        training_repo = TrainingRepository()

        # Protect currently active and any deployed record paths
        deployed_paths = [r.checkpoint_path for r in deployment_repo.list_all() if r.checkpoint_path]
        protected_paths = [ _abs_path(p) for p in deployed_paths ]
        # Also protect any job candidate_checkpoint in progress
        inuse_paths = [j.candidate_checkpoint for j in training_repo.find_all_jobs_with_candidate_checkpoints() if j.candidate_checkpoint]
        protected_paths += [ _abs_path(p) for p in inuse_paths ]

        # Query rejected candidates ordered newest first
        rejected = candidate_repo.find_rejected_candidates_ordered()
        if not rejected:
            return
            
        # Keep newest N
        keep_n = settings.max_rejected_candidates if settings.max_rejected_candidates >= 0 else 0
        to_keep = rejected[:keep_n]
        to_prune = rejected[keep_n:]

        # For each candidate to prune, if checkpoint exists and not protected, delete file and set checkpoint_pruned_at
        for c in to_prune:
            if c.checkpoint_pruned_at:
                continue
            stored = c.stored_path
            abs_stored = _abs_path(stored)
            if not abs_stored or not os.path.exists(abs_stored):
                # Nothing to prune but mark as pruned
                candidate_repo.update(c.candidate_id, {"checkpoint_pruned_at": datetime.utcnow()})
                continue
            # Ensure safety
            deleted = _safe_delete_file(abs_stored, allowed_dirs, protected_paths)
            if deleted:
                candidate_repo.update(c.candidate_id, {"checkpoint_pruned_at": datetime.utcnow()})
    except Exception as e:
        logger.error("cleanup_rejected_candidates failed: %s", e, exc_info=True)


def cleanup_backups():
    """
    Keep only newest `settings.max_backups` files in models/backups while protecting
    current active model and any checkpoint paths referenced by DeployedModelRecord or TrainingJob.
    """
    try:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        backups_dir = os.path.join(backend_dir, "models", "backups")
        os.makedirs(backups_dir, exist_ok=True)
        allowed_dirs = [backups_dir]

        deployment_repo = DeploymentRepository()
        training_repo = TrainingRepository()

        # Protected paths: active model, all deployed checkpoint paths, training job candidate checkpoints
        protected = []
        active = deployment_repo.find_active()
        if active and active.checkpoint_path:
            protected.append(_abs_path(active.checkpoint_path))
        deployed_paths = [r.checkpoint_path for r in deployment_repo.list_all() if r.checkpoint_path]
        protected += [ _abs_path(p) for p in deployed_paths ]
        inuse_paths = [j.candidate_checkpoint for j in training_repo.find_all_jobs_with_candidate_checkpoints() if j.candidate_checkpoint]
        protected += [ _abs_path(p) for p in inuse_paths ]

        # List backup files sorted by modified time desc (newest first)
        files = [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if os.path.isfile(os.path.join(backups_dir, f))]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        keep_n = settings.max_backups if settings.max_backups >= 0 else 0
        to_delete = files[keep_n:]
        for p in to_delete:
            if p in protected:
                logger.info("Skipping protected backup: %s", p)
                continue
            _safe_delete_file(p, allowed_dirs, protected)
    except Exception as e:
        logger.error("cleanup_backups failed: %s", e, exc_info=True)


def cleanup_training_logs():
    try:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        logs_dir = os.path.join(backend_dir, "data", "training_logs")
        if not os.path.exists(logs_dir):
            return
        retention_days = settings.training_log_retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        for fname in os.listdir(logs_dir):
            fpath = os.path.join(logs_dir, fname)
            if not os.path.isfile(fpath):
                continue
            mtime = datetime.utcfromtimestamp(os.path.getmtime(fpath))
            if mtime < cutoff:
                try:
                    os.remove(fpath)
                    logger.info("Removed old training log: %s", fpath)
                except Exception as e:
                    logger.error("Failed to remove training log %s: %s", fpath, e)
    except Exception as e:
        logger.error("cleanup_training_logs failed: %s", e, exc_info=True)


def run_model_retention_cleanup():
    """Run all retention cleanups. Safe and idempotent."""
    try:
        cleanup_rejected_candidates()
        cleanup_backups()
        cleanup_training_logs()
    except Exception as e:
        logger.error("run_model_retention_cleanup failed: %s", e, exc_info=True)
