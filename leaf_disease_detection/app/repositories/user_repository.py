from datetime import datetime
import uuid
from app.database import get_mongo_db, DocumentWrapper
from pymongo.errors import DuplicateKeyError

class UserRepository:
    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db["users"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        try:
            self.collection.create_index("email", unique=True)
            self.collection.create_index("user_id", unique=True)
        except Exception:
            pass

    def find_by_email(self, email):
        if not email:
            return None
        doc = self.collection.find_one({"email": email.strip().lower()})
        return DocumentWrapper(doc) if doc else None

    def find_by_id(self, user_id):
        doc = self.collection.find_one({"user_id": str(user_id)})
        return DocumentWrapper(doc) if doc else None

    def list_all(self):
        cursor = self.collection.find().sort("created_at", -1)
        return [DocumentWrapper(doc) for doc in cursor]

    def _get_next_id(self):
        return "USR-" + uuid.uuid4().hex[:8].upper()

    def create(self, data):
        if isinstance(data, DocumentWrapper):
            doc_dict = data.to_dict()
        else:
            doc_dict = dict(data)
        
        if "user_id" not in doc_dict:
            doc_dict["user_id"] = self._get_next_id()
        if "created_at" not in doc_dict:
            doc_dict["created_at"] = datetime.utcnow()
        if "updated_at" not in doc_dict:
            doc_dict["updated_at"] = datetime.utcnow()
        if "is_active" not in doc_dict:
            doc_dict["is_active"] = True
        if "role" not in doc_dict:
            doc_dict["role"] = "USER"
        
        if "email" in doc_dict:
            doc_dict["email"] = doc_dict["email"].strip().lower()
            
        try:
            self.collection.insert_one(doc_dict)
        except DuplicateKeyError:
            raise ValueError("Email or User ID already exists")
        return DocumentWrapper(doc_dict)

    def update(self, user_id, update_fields):
        if isinstance(update_fields, DocumentWrapper):
            update_dict = update_fields.to_dict()
        else:
            update_dict = dict(update_fields)
            
        update_dict.pop("_id", None)
        update_dict.pop("user_id", None)
        update_dict["updated_at"] = datetime.utcnow()
        
        if "email" in update_dict:
            update_dict["email"] = update_dict["email"].strip().lower()
        
        self.collection.update_one({"user_id": str(user_id)}, {"$set": update_dict})
        return self.find_by_id(user_id)

    def count(self):
        return self.collection.count_documents({})
