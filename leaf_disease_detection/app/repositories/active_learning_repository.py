from datetime import datetime
from app.database import get_mongo_db, DocumentWrapper

class ActiveLearningRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.batch_collection = self.db["active_learning_batches"]
        self.sample_collection = self.db["active_learning_batch_samples"]

    def find_batch_by_id(self, batch_id):
        doc = self.batch_collection.find_one({"batch_id": batch_id})
        return DocumentWrapper(doc) if doc else None

    def list_all_batches(self):
        cursor = self.batch_collection.find().sort("created_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def create_batch(self, data):
        if isinstance(data, DocumentWrapper):
            doc_dict = data.to_dict()
        else:
            doc_dict = dict(data)
        
        if "created_at" not in doc_dict:
            doc_dict["created_at"] = datetime.utcnow()
        if "status" not in doc_dict:
            doc_dict["status"] = "READY"
        if "export_count" not in doc_dict:
            doc_dict["export_count"] = 0
            
        self.batch_collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def update_batch(self, batch_id, update_fields):
        if isinstance(update_fields, DocumentWrapper):
            update_dict = update_fields.to_dict()
        else:
            update_dict = dict(update_fields)
            
        update_dict.pop("_id", None)
        update_dict.pop("batch_id", None)
        
        self.batch_collection.update_one({"batch_id": batch_id}, {"$set": update_dict})
        return self.find_batch_by_id(batch_id)

    def add_batch_sample(self, batch_id, case_id):
        doc_dict = {
            "batch_id": batch_id,
            "case_id": case_id,
            "added_at": datetime.utcnow()
        }
        self.sample_collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def find_samples_by_batch_id(self, batch_id):
        # Find all mappings
        cursor_mappings = self.sample_collection.find({"batch_id": batch_id})
        case_ids = [m["case_id"] for m in cursor_mappings]
        if not case_ids:
            return []
        # Find all prediction cases matching those case IDs
        cursor_cases = self.db["prediction_cases"].find({"case_id": {"$in": case_ids}})
        return [DocumentWrapper(doc) for doc in cursor_cases]

    def count_batch_samples(self, batch_id):
        return self.sample_collection.count_documents({"batch_id": batch_id})

    def get_all_batch_sample_case_ids(self):
        # Utility to get all case IDs that are already included in any batch
        cursor = self.sample_collection.find({}, {"case_id": 1, "_id": 0})
        return {doc["case_id"] for doc in cursor if "case_id" in doc}
