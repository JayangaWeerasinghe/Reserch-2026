from datetime import datetime
from app.database import get_mongo_db, DocumentWrapper

class CandidateRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db["candidate_models"]

    def find_by_candidate_id(self, candidate_id):
        doc = self.collection.find_one({"candidate_id": candidate_id})
        return DocumentWrapper(doc) if doc else None

    def list_all(self):
        cursor = self.collection.find().sort("uploaded_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def count_rejected_kept(self):
        return self.collection.count_documents({
            "status": "REJECTED_BY_METRICS",
            "checkpoint_pruned_at": None
        })

    def find_rejected_candidates_ordered(self):
        cursor = self.collection.find({
            "status": "REJECTED_BY_METRICS"
        }).sort("uploaded_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def create(self, data):
        if isinstance(data, DocumentWrapper):
            doc_dict = data.to_dict()
        else:
            doc_dict = dict(data)
            
        if "uploaded_at" not in doc_dict:
            doc_dict["uploaded_at"] = datetime.utcnow()
        if "checkpoint_pruned_at" not in doc_dict:
            doc_dict["checkpoint_pruned_at"] = None
            
        self.collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def update(self, candidate_id, update_fields):
        if isinstance(update_fields, DocumentWrapper):
            update_dict = update_fields.to_dict()
        else:
            update_dict = dict(update_fields)
            
        update_dict.pop("_id", None)
        update_dict.pop("candidate_id", None)
        
        self.collection.update_one({"candidate_id": candidate_id}, {"$set": update_dict})
        return self.find_by_candidate_id(candidate_id)
