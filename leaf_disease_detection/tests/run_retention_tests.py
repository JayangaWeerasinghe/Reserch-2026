import os
import tempfile
import time
from datetime import datetime, timedelta
from pymongo import MongoClient

# Setup imports from app
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.config import settings

# Force the settings to point to a test DB name
settings.mongodb_uri = "mongodb://localhost:27017/paddyguard_test"

from app.repositories.candidate_repository import CandidateRepository
from app.repositories.deployment_repository import DeploymentRepository
from app.repositories.training_repository import TrainingRepository
from training import model_retention

def touch(path, age_seconds=0):
    with open(path, 'w') as f:
        f.write('test')
    if age_seconds:
        past = time.time() - age_seconds
        os.utime(path, (past, past))


def run_tests():
    # Connect and clear test database
    client = MongoClient("mongodb://localhost:27017")
    db = client["paddyguard_test"]
    db["candidate_models"].delete_many({})
    db["deployed_models"].delete_many({})
    db["training_jobs"].delete_many({})

    candidate_repo = CandidateRepository()
    deployment_repo = DeploymentRepository()
    training_repo = TrainingRepository()

    tmp = tempfile.TemporaryDirectory()
    temp_backend = tmp.name
    try:
        # Create fake backend structure
        training_dir = os.path.join(temp_backend, 'training')
        models_dir = os.path.join(temp_backend, 'models')
        candidates_dir = os.path.join(models_dir, 'candidates')
        backups_dir = os.path.join(models_dir, 'backups')
        data_logs = os.path.join(temp_backend, 'data', 'training_logs')
        os.makedirs(candidates_dir, exist_ok=True)
        os.makedirs(backups_dir, exist_ok=True)
        os.makedirs(data_logs, exist_ok=True)
        os.makedirs(os.path.join(temp_backend, 'data'), exist_ok=True)

        # Monkeypatch model_retention.__file__ so functions compute backend_dir inside temp
        fake_module_file = os.path.join(training_dir, 'model_retention.py')
        os.makedirs(training_dir, exist_ok=True)
        open(fake_module_file, 'a').close()
        model_retention.__file__ = fake_module_file

        # Create active model (protected)
        active_model_path = os.path.join(models_dir, 'active_model_test.pth')
        touch(active_model_path)
        
        deployment_repo.create({
            "id": 1,
            "checkpoint_path": active_model_path,
            "test_accuracy": 0.99,
            "macro_f1": 0.99,
            "is_active": True
        })

        # Create 5 rejected candidate files (oldest to newest)
        candidates = []
        now = datetime.utcnow()
        for i in range(5):
            fname = f'candidate_test_{i}.pth'
            path = os.path.join(candidates_dir, fname)
            touch(path)
            os.utime(path, (time.time() - (5000 - i*1000), time.time() - (5000 - i*1000)))
            
            candidate_repo.create({
                "candidate_id": f'C{i}',
                "filename": fname,
                "stored_path": path,
                "test_accuracy": 0.9+i*0.001,
                "macro_f1": 0.9+i*0.001,
                "status": 'REJECTED_BY_METRICS',
                "uploaded_at": now - timedelta(days=(5-i))
            })
            candidates.append((f'C{i}', path))

        # Add one eligible candidate which must be protected
        eligible_path = os.path.join(candidates_dir, 'candidate_eligible.pth')
        touch(eligible_path)
        
        candidate_repo.create({
            "candidate_id": 'ELIG',
            "filename": 'candidate_eligible.pth',
            "stored_path": eligible_path,
            "test_accuracy": 0.995,
            "macro_f1": 0.995,
            "status": 'ELIGIBLE_FOR_REVIEW',
            "uploaded_at": now
        })

        # Create 4 backup files
        backup_paths = []
        for i in range(4):
            bp = os.path.join(backups_dir, f'backup_test_{i}.pth')
            touch(bp)
            os.utime(bp, (time.time() - (4000 - i*1000), time.time() - (4000 - i*1000)))
            backup_paths.append(bp)

        # Create training logs (one old, one new)
        old_log = os.path.join(data_logs, 'old.log')
        new_log = os.path.join(data_logs, 'new.log')
        touch(old_log)
        touch(new_log)
        old_age = 15 * 24 * 3600
        os.utime(old_log, (time.time() - old_age, time.time() - old_age))

        # Run cleanups
        print('Before cleanup: candidates files:', os.listdir(candidates_dir))
        model_retention.cleanup_rejected_candidates()
        print('After pruning rejected: candidates files:', os.listdir(candidates_dir))

        # Verify pruned count: only newest 3 should remain (MAX_REJECTED_CANDIDATES default 3)
        remaining = [f for f in os.listdir(candidates_dir) if f.startswith('candidate_test_')]
        print('Remaining rejected candidate files:', remaining)
        assert len(remaining) == 3, f'Expected 3 rejected candidates kept, found {len(remaining)}'

        # Verify DB records still exist and pruned ones have checkpoint_pruned_at set
        all_cands = candidate_repo.list_all()
        pruned_count = sum(1 for c in all_cands if c.checkpoint_pruned_at is not None)
        print('Pruned DB count:', pruned_count)
        assert pruned_count >= 2, 'Expected at least 2 pruned DB records'

        # Ensure eligible candidate still present on disk
        assert os.path.exists(eligible_path), 'Eligible candidate should not be deleted'

        # Backups cleanup
        print('Backups before:', os.listdir(backups_dir))
        model_retention.cleanup_backups()
        backups_after = os.listdir(backups_dir)
        print('Backups after:', backups_after)
        assert len(backups_after) == 2, f'Expected 2 backups kept, found {len(backups_after)}'

        # Training logs cleanup
        model_retention.cleanup_training_logs()
        logs_after = os.listdir(data_logs)
        print('Training logs after:', logs_after)
        assert 'old.log' not in logs_after and 'new.log' in logs_after, 'Old log should be removed, new log kept'

        # Idempotence: run again
        model_retention.cleanup_rejected_candidates()
        model_retention.cleanup_backups()
        model_retention.cleanup_training_logs()
        print('Idempotence run succeeded')

        print('All retention tests passed')

    finally:
        db["candidate_models"].delete_many({})
        db["deployed_models"].delete_many({})
        db["training_jobs"].delete_many({})
        client.close()
        tmp.cleanup()

if __name__ == '__main__':
    run_tests()
