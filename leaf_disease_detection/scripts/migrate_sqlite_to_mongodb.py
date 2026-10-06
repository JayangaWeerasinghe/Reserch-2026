import os
import sys
import argparse
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader

# Load environment variables
load_dotenv()

# Setup system paths so we can import app modules if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Get configs
MONGODB_URI = os.getenv("MONGODB_URI", "")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "paddyguard.db")
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
GRADCAM_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gradcam")

def validate_env(is_dry_run):
    missing = []
    if not MONGODB_URI:
        missing.append("MONGODB_URI")
    if not CLOUDINARY_CLOUD_NAME:
        missing.append("CLOUDINARY_CLOUD_NAME")
    if not CLOUDINARY_API_KEY:
        missing.append("CLOUDINARY_API_KEY")
    if not CLOUDINARY_API_SECRET:
        missing.append("CLOUDINARY_API_SECRET")
        
    if missing:
        mode_str = "DRY-RUN" if is_dry_run else "REAL MIGRATION"
        print(f"\n============================================================")
        print(f"CRITICAL ERROR: Environment Configuration Missing for {mode_str}")
        print(f"============================================================")
        print(f"The following environment variables are missing or empty in your backend/.env:")
        for m in missing:
            print(f" - {m}")
        print(f"\nPlease configure these credentials in backend/.env before running this script.")
        print(f"============================================================\n")
        return False
    return True

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def run_migration(is_dry_run=True):
    print("============================================================")
    print(f"PaddyGuard Migration Tool: Running in {'DRY-RUN' if is_dry_run else 'REAL'} Mode")
    print("============================================================")

    # 1. Validate variables
    if not validate_env(is_dry_run):
        sys.exit(1)

    # 2. Connect to SQLite
    if not os.path.exists(DB_PATH):
        print(f"CRITICAL ERROR: SQLite database not found at {DB_PATH}. Nothing to migrate.")
        sys.exit(1)
        
    sql_conn = sqlite3.connect(DB_PATH)
    sql_conn.row_factory = dict_factory
    sql_cur = sql_conn.cursor()

    # 3. Connect to MongoDB
    try:
        db_name = "paddyguard"
        from urllib.parse import urlparse
        parsed = urlparse(MONGODB_URI)
        if parsed.path and parsed.path.strip("/"):
            db_name = parsed.path.strip("/")
            
        mongo_client = MongoClient(MONGODB_URI)
        mongo_db = mongo_client[db_name]
        # Verify connection
        mongo_client.admin.command('ping')
        print(f"Connected to MongoDB successfully. Target Database: '{db_name}'")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to MongoDB: {e}")
        sql_conn.close()
        sys.exit(1)

    # 4. Connect to Cloudinary
    try:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True
        )
        print("Configured Cloudinary client successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to configure Cloudinary: {e}")
        sql_conn.close()
        sys.exit(1)

    # Helper function to get row count in SQLite
    def get_sqlite_count(table_name):
        try:
            sql_cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            return sql_cur.fetchone()["count"]
        except Exception:
            return 0

    # Fetch counts
    counts = {
        "prediction_cases": get_sqlite_count("prediction_cases"),
        "expert_users": get_sqlite_count("expert_users"),
        "active_learning_batches": get_sqlite_count("active_learning_batches"),
        "active_learning_batch_samples": get_sqlite_count("active_learning_batch_samples"),
        "candidate_models": get_sqlite_count("candidate_models"),
        "training_jobs": get_sqlite_count("training_jobs"),
        "deployed_model_records": get_sqlite_count("deployed_model_records")
    }

    print("\n--- SQLite Source Statistics ---")
    for k, v in counts.items():
        print(f" - {k}: {v} records")

    # Check local media assets
    local_originals = 0
    local_gradcams = 0
    missing_originals = 0
    missing_gradcams = 0

    try:
        sql_cur.execute("SELECT case_id, image_name, gradcam_image_name FROM prediction_cases")
        cases = sql_cur.fetchall()
        for c in cases:
            if c["image_name"]:
                orig_path = os.path.join(UPLOADS_DIR, c["image_name"])
                if os.path.exists(orig_path):
                    local_originals += 1
                else:
                    missing_originals += 1
            if c["gradcam_image_name"]:
                gc_path = os.path.join(GRADCAM_DIR, c["gradcam_image_name"])
                if os.path.exists(gc_path):
                    local_gradcams += 1
                else:
                    missing_gradcams += 1
    except Exception as e:
        print(f"Warning: Failed to analyze SQLite media references: {e}")
        cases = []

    print("\n--- Media Files Analysis ---")
    print(f" - Original images found locally: {local_originals}")
    print(f" - Original images missing locally: {missing_originals}")
    print(f" - Grad-CAM overlays found locally: {local_gradcams}")
    print(f" - Grad-CAM overlays missing locally: {missing_gradcams}")

    if is_dry_run:
        print("\n============================================================")
        print("DRY-RUN SUMMARY REPORT SUCCESSFUL")
        print("============================================================")
        print("No changes were made to SQLite or MongoDB.")
        print("No files were uploaded to Cloudinary.")
        print("Please run without --dry-run flag to perform real migration.")
        print("============================================================\n")
        sql_conn.close()
        mongo_client.close()
        return

    # Real Migration Logic
    print("\n============================================================")
    print("STARTING REAL MIGRATION WITH IDEMPOTENT UPSERTS")
    print("============================================================\n")

    summary = {
        "expert_users": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "prediction_cases": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "active_learning_batches": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "active_learning_batch_samples": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "candidate_models": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "training_jobs": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "deployed_models": {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0},
        "media_uploads": {"originals_uploaded": 0, "gradcams_uploaded": 0, "skipped": 0, "errors": 0}
    }

    # Helper function to convert SQLite ISO strings or timestamps to datetime objects
    def parse_datetime(val):
        if not val:
            return None
        # SQLite datetime format could be 'YYYY-MM-DD HH:MM:SS.mmmmmm'
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                pass
        return val

    # 1. Migrate expert_users
    print("Migrating expert_users...")
    try:
        sql_cur.execute("SELECT * FROM expert_users")
        rows = sql_cur.fetchall()
        for r in rows:
            # Map fields
            doc = {
                "id": r["id"],
                "name": r["name"],
                "username": r["username"],
                "password_hash": r["password_hash"],
                "role": r["role"],
                "is_active": bool(r["is_active"]),
                "created_at": parse_datetime(r["created_at"]),
                "created_by": r["created_by"]
            }
            existing = mongo_db["expert_users"].find_one({"username": doc["username"]})
            if existing:
                mongo_db["expert_users"].replace_one({"username": doc["username"]}, doc)
                summary["expert_users"]["updated"] += 1
            else:
                mongo_db["expert_users"].insert_one(doc)
                summary["expert_users"]["inserted"] += 1
    except Exception as e:
        print(f"Error migrating expert_users: {e}")
        summary["expert_users"]["errors"] += 1

    # 2. Migrate prediction_cases
    print("Migrating prediction_cases & uploading media to Cloudinary (this might take a few minutes)...")
    for c in cases:
        try:
            sql_cur.execute("SELECT * FROM prediction_cases WHERE case_id = ?", (c["case_id"],))
            r = sql_cur.fetchone()
            if not r:
                continue

            # Original media upload
            image_url = None
            image_public_id = None
            if r["image_name"]:
                local_path = os.path.join(UPLOADS_DIR, r["image_name"])
                if os.path.exists(local_path):
                    # Check if already uploaded/migrated in Mongo
                    existing_case = mongo_db["prediction_cases"].find_one({"case_id": r["case_id"]})
                    if existing_case and existing_case.get("image_url") and existing_case.get("image_public_id"):
                        image_url = existing_case["image_url"]
                        image_public_id = existing_case["image_public_id"]
                        summary["media_uploads"]["skipped"] += 1
                    else:
                        print(f"Uploading original image for case {r['case_id']}...")
                        res = cloudinary.uploader.upload(local_path, folder="paddyguard/originals")
                        image_url = res.get("secure_url")
                        image_public_id = res.get("public_id")
                        summary["media_uploads"]["originals_uploaded"] += 1
                else:
                    print(f"Warning: Local original image {r['image_name']} missing for case {r['case_id']}")

            # Grad-CAM media upload
            gradcam_url = None
            gradcam_public_id = None
            if r["gradcam_image_name"]:
                local_path = os.path.join(GRADCAM_DIR, r["gradcam_image_name"])
                if os.path.exists(local_path):
                    existing_case = mongo_db["prediction_cases"].find_one({"case_id": r["case_id"]})
                    if existing_case and existing_case.get("gradcam_url") and existing_case.get("gradcam_public_id"):
                        gradcam_url = existing_case["gradcam_url"]
                        gradcam_public_id = existing_case["gradcam_public_id"]
                    else:
                        print(f"Uploading Grad-CAM overlay for case {r['case_id']}...")
                        res = cloudinary.uploader.upload(local_path, folder="paddyguard/gradcam")
                        gradcam_url = res.get("secure_url")
                        gradcam_public_id = res.get("public_id")
                        summary["media_uploads"]["gradcams_uploaded"] += 1
                else:
                    print(f"Warning: Local Grad-CAM overlay {r['gradcam_image_name']} missing for case {r['case_id']}")

            doc = {
                "id": r["id"],
                "case_id": r["case_id"],
                "created_at": parse_datetime(r["created_at"]),
                "image_name": r["image_name"],
                "image_url": image_url,
                "image_public_id": image_public_id,
                "gradcam_image_name": r["gradcam_image_name"],
                "gradcam_url": gradcam_url,
                "gradcam_public_id": gradcam_public_id,
                "predicted_disease": r["predicted_disease"],
                "confidence": r["confidence"],
                "status": r["status"],
                "severity_percentage": r["severity_percentage"],
                "severity_level": r["severity_level"],
                "city": r["city"],
                "district": r["district"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "field_area_acres": r["field_area_acres"],
                "affected_field_percentage": r["affected_field_percentage"],
                "rice_variety": r["rice_variety"],
                "growth_stage": r["growth_stage"],
                "expected_yield_kg_per_acre": r["expected_yield_kg_per_acre"],
                "treatment_applied": bool(r["treatment_applied"]),
                "weather_json": r["weather_json"],
                "predicted_loss_percentage": r["predicted_loss_percentage"],
                "estimated_loss_kg": r["estimated_loss_kg"],
                "farmer_confirmation": r["farmer_confirmation"],
                "expert_validated_disease": r["expert_validated_disease"],
                "actual_harvest_kg": r["actual_harvest_kg"],
                "expected_healthy_harvest_kg": r["expected_healthy_harvest_kg"],
                "approved_for_training": bool(r["approved_for_training"]),
                "is_low_confidence": bool(r["is_low_confidence"]),
                "energy_score": r["energy_score"],
                "needs_expert_review": bool(r["needs_expert_review"]),
                "review_status": r["review_status"],
                "review_reason": r["review_reason"],
                "verified_at": parse_datetime(r["verified_at"]),
                "consumed_by_job_id": r["consumed_by_job_id"]
            }

            existing = mongo_db["prediction_cases"].find_one({"case_id": doc["case_id"]})
            if existing:
                mongo_db["prediction_cases"].replace_one({"case_id": doc["case_id"]}, doc)
                summary["prediction_cases"]["updated"] += 1
            else:
                mongo_db["prediction_cases"].insert_one(doc)
                summary["prediction_cases"]["inserted"] += 1
        except Exception as e:
            print(f"Error migrating prediction case {c['case_id']}: {e}")
            summary["prediction_cases"]["errors"] += 1

    # 3. Migrate active_learning_batches
    print("Migrating active_learning_batches...")
    try:
        sql_cur.execute("SELECT * FROM active_learning_batches")
        rows = sql_cur.fetchall()
        for r in rows:
            doc = {
                "id": r["id"],
                "batch_id": r["batch_id"],
                "created_at": parse_datetime(r["created_at"]),
                "sample_count": r["sample_count"],
                "status": r["status"],
                "is_demo_mode": bool(r["is_demo_mode"]),
                "recommended_batch_size": r["recommended_batch_size"],
                "source": r["source"],
                "exported_at": parse_datetime(r["exported_at"]),
                "export_count": r["export_count"]
            }
            existing = mongo_db["active_learning_batches"].find_one({"batch_id": doc["batch_id"]})
            if existing:
                mongo_db["active_learning_batches"].replace_one({"batch_id": doc["batch_id"]}, doc)
                summary["active_learning_batches"]["updated"] += 1
            else:
                mongo_db["active_learning_batches"].insert_one(doc)
                summary["active_learning_batches"]["inserted"] += 1
    except Exception as e:
        print(f"Error migrating active_learning_batches: {e}")
        summary["active_learning_batches"]["errors"] += 1

    # 4. Migrate active_learning_batch_samples
    print("Migrating active_learning_batch_samples...")
    try:
        sql_cur.execute("SELECT * FROM active_learning_batch_samples")
        rows = sql_cur.fetchall()
        for r in rows:
            doc = {
                "id": r["id"],
                "batch_id": r["batch_id"],
                "case_id": r["case_id"],
                "added_at": parse_datetime(r["added_at"])
            }
            existing = mongo_db["active_learning_batch_samples"].find_one({"batch_id": doc["batch_id"], "case_id": doc["case_id"]})
            if existing:
                summary["active_learning_batch_samples"]["skipped"] += 1
            else:
                mongo_db["active_learning_batch_samples"].insert_one(doc)
                summary["active_learning_batch_samples"]["inserted"] += 1
    except Exception as e:
        print(f"Error migrating active_learning_batch_samples: {e}")
        summary["active_learning_batch_samples"]["errors"] += 1

    # 5. Migrate candidate_models
    print("Migrating candidate_models...")
    try:
        sql_cur.execute("SELECT * FROM candidate_models")
        rows = sql_cur.fetchall()
        for r in rows:
            doc = {
                "id": r["id"],
                "candidate_id": r["candidate_id"],
                "filename": r["filename"],
                "stored_path": r["stored_path"],
                "uploaded_at": parse_datetime(r["uploaded_at"]),
                "test_accuracy": r["test_accuracy"],
                "macro_f1": r["macro_f1"],
                "source_batch_id": r["source_batch_id"],
                "notes": r["notes"],
                "status": r["status"],
                "training_job_id": r["training_job_id"],
                "checkpoint_pruned_at": parse_datetime(r["checkpoint_pruned_at"])
            }
            existing = mongo_db["candidate_models"].find_one({"candidate_id": doc["candidate_id"]})
            if existing:
                mongo_db["candidate_models"].replace_one({"candidate_id": doc["candidate_id"]}, doc)
                summary["candidate_models"]["updated"] += 1
            else:
                mongo_db["candidate_models"].insert_one(doc)
                summary["candidate_models"]["inserted"] += 1
    except Exception as e:
        print(f"Error migrating candidate_models: {e}")
        summary["candidate_models"]["errors"] += 1

    # 6. Migrate training_jobs
    print("Migrating training_jobs...")
    try:
        sql_cur.execute("SELECT * FROM training_jobs")
        rows = sql_cur.fetchall()
        for r in rows:
            doc = {
                "id": r["id"],
                "job_id": r["job_id"],
                "status": r["status"],
                "created_at": parse_datetime(r["created_at"]),
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
                "source_sample_count": r["source_sample_count"],
                "base_checkpoint": r["base_checkpoint"],
                "candidate_checkpoint": r["candidate_checkpoint"],
                "baseline_accuracy": r["baseline_accuracy"],
                "baseline_macro_f1": r["baseline_macro_f1"],
                "candidate_accuracy": r["candidate_accuracy"],
                "candidate_macro_f1": r["candidate_macro_f1"],
                "accuracy_delta": r["accuracy_delta"],
                "f1_delta": r["f1_delta"],
                "decision": r["decision"],
                "error_message": r["error_message"],
                "log_tail": r["log_tail"],
                "epochs_completed": r["epochs_completed"],
                "total_epochs": r["total_epochs"]
            }
            existing = mongo_db["training_jobs"].find_one({"job_id": doc["job_id"]})
            if existing:
                mongo_db["training_jobs"].replace_one({"job_id": doc["job_id"]}, doc)
                summary["training_jobs"]["updated"] += 1
            else:
                mongo_db["training_jobs"].insert_one(doc)
                summary["training_jobs"]["inserted"] += 1
    except Exception as e:
        print(f"Error migrating training_jobs: {e}")
        summary["training_jobs"]["errors"] += 1

    # 7. Migrate deployed_models
    print("Migrating deployed_models...")
    try:
        sql_cur.execute("SELECT * FROM deployed_model_records")
        rows = sql_cur.fetchall()
        for r in rows:
            doc = {
                "id": r["id"],
                "checkpoint_path": r["checkpoint_path"],
                "test_accuracy": r["test_accuracy"],
                "macro_f1": r["macro_f1"],
                "deployed_at": parse_datetime(r["deployed_at"]),
                "deployed_by": r["deployed_by"],
                "notes": r["notes"],
                "is_active": bool(r["is_active"])
            }
            existing = mongo_db["deployed_models"].find_one({"id": doc["id"]})
            if existing:
                mongo_db["deployed_models"].replace_one({"id": doc["id"]}, doc)
                summary["deployed_models"]["updated"] += 1
            else:
                mongo_db["deployed_models"].insert_one(doc)
                summary["deployed_models"]["inserted"] += 1
    except Exception as e:
        print(f"Error migrating deployed_models: {e}")
        summary["deployed_models"]["errors"] += 1

    sql_conn.close()
    mongo_client.close()

    print("\n============================================================")
    print("REAL MIGRATION COMPLETED SUCCESSFULLY")
    print("============================================================")
    print("Summary of actions:")
    for key, val in summary.items():
        print(f" - {key}: {val}")
    print("============================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=False, help="Run in dry-run diagnostics mode without making edits")
    args = parser.parse_args()
    
    run_migration(is_dry_run=args.dry_run)
