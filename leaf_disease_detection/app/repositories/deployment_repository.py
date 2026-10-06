from datetime import datetime
from app.database import get_mongo_db, DocumentWrapper

class DeploymentRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db["deployed_models"]

    def find_active(self):
        doc = self.collection.find_one({"is_active": True})
        return DocumentWrapper(doc) if doc else None

    def list_all(self):
        cursor = self.collection.find().sort("deployed_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def _get_next_id(self):
        max_doc = self.collection.find_one(sort=[("id", -1)])
        if max_doc and "id" in max_doc:
            return max_doc["id"] + 1
        return 1

    def create(self, data):
        if isinstance(data, DocumentWrapper):
            doc_dict = data.to_dict()
        else:
            doc_dict = dict(data)
            
        if "id" not in doc_dict:
            doc_dict["id"] = self._get_next_id()
        if "deployed_at" not in doc_dict:
            doc_dict["deployed_at"] = datetime.utcnow()
        if "is_active" not in doc_dict:
            doc_dict["is_active"] = True
            
        self.collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def deactivate_all(self):
        self.collection.update_many({"is_active": True}, {"$set": {"is_active": False}})

    def count_active(self):
        return self.collection.count_documents({"is_active": True})
