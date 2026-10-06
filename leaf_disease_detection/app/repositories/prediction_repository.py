from datetime import datetime
from app.database import get_mongo_db, DocumentWrapper

class PredictionRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db["prediction_cases"]

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value)

    @staticmethod
    def is_pending_review(record):
        if not record:
            return False
        return str(record.get("review_status") or "").lower() == "pending"

    @staticmethod
    def is_verified_record(record):
        if not record:
            return False
        return str(record.get("review_status") or "").lower() == "verified"

    @staticmethod
    def is_ood_label(value):
        if value is None:
            return False
        return str(value).strip().upper() in {"OOD", "UNKNOWN", "OUT_OF_DISTRIBUTION"}

    @staticmethod
    def is_approved_for_training(record):
        if not record:
            return False
        if not PredictionRepository.is_verified_record(record):
            return False
        if str(record.get("status") or "").strip().upper() == "OOD":
            return False
        expert_label = record.get("expert_validated_disease")
        if PredictionRepository.is_ood_label(expert_label):
            return False
        if expert_label is None or str(expert_label).strip() == "":
            return False

        approved = record.get("approved_for_training")
        if approved is None:
            return True
        return PredictionRepository._as_bool(approved) is True

    @staticmethod
    def is_unused_approved_training_sample(record):
        if not PredictionRepository.is_approved_for_training(record):
            return False

        consumed = record.get("consumed_by_job_id")
        if consumed is None:
            return True
        if isinstance(consumed, str) and consumed.strip() == "":
            return True
        return False

    @staticmethod
    def is_consumed_training_sample(record):
        if not record:
            return False
        consumed = record.get("consumed_by_job_id")
        if consumed is None:
            return False
        if isinstance(consumed, str):
            return consumed.strip() != ""
        return True

    @staticmethod
    def is_active_learning_eligible(record):
        return PredictionRepository.is_unused_approved_training_sample(record)

    def find_by_case_id(self, case_id):
        doc = self.collection.find_one({"case_id": case_id})
        return DocumentWrapper(doc) if doc else None

    def find_top_k_candidates(self, limit=5):
        # Top-K uncertainty cases: status != OOD, needs_expert_review is False, review_status is "pending"
        cursor = self.collection.find({
            "status": {"$ne": "OOD"},
            "needs_expert_review": {"$ne": True},
            "review_status": "pending"
        }).sort("confidence", 1).limit(limit)
        return [DocumentWrapper(doc) for doc in cursor]

    def find_pending_reviews(self):
        # Needs expert review, review status is pending, and reason is LOW_CONFIDENCE
        cursor = self.collection.find({
            "needs_expert_review": True,
            "review_status": "pending",
            "review_reason": "LOW_CONFIDENCE"
        }).sort("confidence", 1)
        return [DocumentWrapper(doc) for doc in cursor]

    def find_verified_unused_samples(self, exclude_case_ids=None):
        query = {
            "status": {"$ne": "OOD"},
            "expert_validated_disease": {"$nin": ["", None, "OOD", "Unknown", "UNKNOWN"]},
            "review_status": "verified",
            "approved_for_training": True,
            "$or": [
                {"consumed_by_job_id": {"$exists": False}},
                {"consumed_by_job_id": None},
                {"consumed_by_job_id": ""}
            ]
        }
        if exclude_case_ids:
            query["case_id"] = {"$nin": list(exclude_case_ids)}
        cursor = self.collection.find(query)
        return [DocumentWrapper(doc) for doc in cursor]

    def find_eligible_fine_tune_samples(self):
        cursor = self.collection.find({
            "status": {"$ne": "OOD"},
            "expert_validated_disease": {"$nin": ["", None, "OOD", "Unknown", "UNKNOWN"]},
            "review_status": "verified",
            "approved_for_training": True,
            "$or": [
                {"consumed_by_job_id": {"$exists": False}},
                {"consumed_by_job_id": None},
                {"consumed_by_job_id": ""}
            ]
        })
        return [DocumentWrapper(doc) for doc in cursor]

    def find_review_queue_records(self, top_k_limit=5):
        """Full records currently shown in the Expert Review Queue.

        Mirrors the exact union used by list_review_queue(): LOW_CONFIDENCE
        pending records plus the current top-K borderline-uncertainty pending
        records. Used only to compute a safe, restrictive id set for bulk
        clearing of the pending queue - never touches verified/approved/
        consumed records because both source queries require
        review_status == "pending".
        """
        seen = {}
        for r in self.find_pending_reviews():
            seen[r.case_id] = r
        for r in self.find_top_k_candidates(limit=top_k_limit):
            seen.setdefault(r.case_id, r)
        return list(seen.values())

    def delete_pending_review_queue_records(self, case_ids):
        """Bulk-delete only records that are still pending review among case_ids.

        Restrictive, explicit filter (case_id in a known-safe id set AND
        review_status == "pending") - never an unrestricted delete_many({}).
        Guards against a race where a record was verified/approved/consumed
        between id lookup and delete.
        """
        if not case_ids:
            return 0
        result = self.collection.delete_many({
            "case_id": {"$in": list(case_ids)},
            "review_status": "pending"
        })
        return result.deleted_count

    def find_by_consumed_job_id(self, job_id):
        cursor = self.collection.find({"consumed_by_job_id": job_id})
        return [DocumentWrapper(doc) for doc in cursor]

    def list_all(self):
        cursor = self.collection.find().sort("created_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def count_pending_expert_reviews(self):
        return self.collection.count_documents({
            "review_status": "pending"
        })

    def count_verified_expert_samples(self):
        return self.collection.count_documents({
            "review_status": "verified"
        })

    def count_approved_for_training_samples(self):
        return self.collection.count_documents({
            "status": {"$ne": "OOD"},
            "expert_validated_disease": {"$nin": ["", None, "OOD", "Unknown", "UNKNOWN"]},
            "review_status": "verified",
            "approved_for_training": True
        })

    def count_active_learning_eligible(self):
        return self.collection.count_documents({
            "status": {"$ne": "OOD"},
            "expert_validated_disease": {"$nin": ["", None, "OOD", "Unknown", "UNKNOWN"]},
            "review_status": "verified",
            "approved_for_training": True,
            "$or": [
                {"consumed_by_job_id": {"$exists": False}},
                {"consumed_by_job_id": None},
                {"consumed_by_job_id": ""}
            ]
        })

    def count_consumed_training_samples(self):
        return self.collection.count_documents({
            "consumed_by_job_id": {"$exists": True, "$ne": None, "$ne": ""}
        })

    def count_eligible_fine_tune_samples(self):
        return self.collection.count_documents({
            "status": {"$ne": "OOD"},
            "expert_validated_disease": {"$nin": ["", None, "OOD", "Unknown", "UNKNOWN"]},
            "review_status": "verified",
            "approved_for_training": True,
            "$or": [
                {"consumed_by_job_id": {"$exists": False}},
                {"consumed_by_job_id": None},
                {"consumed_by_job_id": ""}
            ]
        })

    def create(self, data):
        if isinstance(data, DocumentWrapper):
            doc_dict = data.to_dict()
        else:
            doc_dict = dict(data)
        if "created_at" not in doc_dict:
            doc_dict["created_at"] = datetime.utcnow()
        self.collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def update(self, case_id, update_fields):
        if isinstance(update_fields, DocumentWrapper):
            update_dict = update_fields.to_dict()
        else:
            update_dict = dict(update_fields)
        
        # Strip _id if it's there to avoid immutable field error
        update_dict.pop("_id", None)
        
        self.collection.update_one({"case_id": case_id}, {"$set": update_dict})
        return self.find_by_case_id(case_id)

    def count_eligible_fine_tune_samples(self):
        """Count samples eligible for fine-tuning: verified, approved, not yet consumed."""
        return self.collection.count_documents({
            "status": {"$ne": "OOD"},
            "review_status": "verified",
            "approved_for_training": True,
            "consumed_by_job_id": None
        })

    def count_ood_excluded_unconsumed_samples(self):
        """Count unconsumed reviewed samples excluded from fine-tuning due to OOD status/label.

        Read-only helper used for fine-tuning console logging only; does not affect
        eligibility filtering, training selection, or promotion logic.
        """
        return self.collection.count_documents({
            "consumed_by_job_id": None,
            "$or": [
                {"status": "OOD"},
                {"expert_validated_disease": {"$in": ["OOD", "Unknown", "UNKNOWN", "OUT_OF_DISTRIBUTION"]}}
            ]
        })

    def count(self):
        return self.collection.count_documents({})

    def delete(self, case_id):
        result = self.collection.delete_one({"case_id": case_id})
        return result.deleted_count > 0
