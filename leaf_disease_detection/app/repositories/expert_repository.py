from datetime import datetime
from app.database import get_mongo_db, DocumentWrapper

class ExpertRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db["expert_users"]

    def find_by_username(self, username):
        doc = self.collection.find_one({"username": username})
        return DocumentWrapper(doc) if doc else None

    def find_by_id(self, expert_id):
        doc = self.collection.find_one({"id": int(expert_id)})
        return DocumentWrapper(doc) if doc else None

    def list_all(self):
        cursor = self.collection.find().sort("created_at", -1)
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
        if "created_at" not in doc_dict:
            doc_dict["created_at"] = datetime.utcnow()
        if "is_active" not in doc_dict:
            doc_dict["is_active"] = True
        if "role" not in doc_dict:
            doc_dict["role"] = "EXPERT"
            
        self.collection.insert_one(doc_dict)
        return DocumentWrapper(doc_dict)

    def update(self, expert_id, update_fields):
        if isinstance(update_fields, DocumentWrapper):
            update_dict = update_fields.to_dict()
        else:
            update_dict = dict(update_fields)
            
        update_dict.pop("_id", None)
        update_dict.pop("id", None)
        
        self.collection.update_one({"id": int(expert_id)}, {"$set": update_dict})
        return self.find_by_id(expert_id)

    def count(self):
        return self.collection.count_documents({})
