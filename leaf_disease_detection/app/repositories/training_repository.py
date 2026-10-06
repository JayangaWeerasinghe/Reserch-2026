from datetime import datetime
from app.database import get_mongo_db, DocumentWrapper

class TrainingRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db["training_jobs"]

    def find_by_job_id(self, job_id):
        doc = self.collection.find_one({"job_id": job_id})
        return DocumentWrapper(doc) if doc else None

    def list_all(self):
        cursor = self.collection.find().sort("created_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def find_all_jobs_with_candidate_checkpoints(self):
        cursor = self.collection.find({"candidate_checkpoint": {"$ne": None}})
        return [DocumentWrapper(doc) for doc in cursor]

    def create(self, data):
        if isinstance(data, DocumentWrapper):
            doc_dict = data.to_dict()
        else:
            doc_dict = dict(data)
            
        if "created_at" not in doc_dict:
            doc_dict["created_at"] = datetime.utcnow()
        if "status" not in doc_dict:
            doc_dict["status"] = "QUEUED"
        if "epochs_completed" not in doc_dict:
            doc_dict["epochs_completed"] = 0
            
        self.collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def update(self, job_id, update_fields):
        if isinstance(update_fields, DocumentWrapper):
            update_dict = update_fields.to_dict()
        else:
            update_dict = dict(update_fields)
            
        update_dict.pop("_id", None)
        update_dict.pop("job_id", None)
        
        self.collection.update_one({"job_id": job_id}, {"$set": update_dict})
        return self.find_by_job_id(job_id)
