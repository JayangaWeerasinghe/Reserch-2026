import os
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# Programmatically create directories if using SQLite to avoid startup crash
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# MongoDB Client Initialization
_mongo_client = None

def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        uri = settings.mongodb_uri or "mongodb://localhost:27017"
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            client.admin.command('ismaster')
            _mongo_client = client
        except Exception as primary_error:
            # Fallback to local MongoDB if remote URI fails or has DNS issues
            try:
                local_client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
                local_client.admin.command('ismaster')
                _mongo_client = local_client
            except Exception:
                raise primary_error
    return _mongo_client

def get_mongo_db():
    client = get_mongo_client()
    uri = settings.mongodb_uri or "mongodb://localhost:27017"
    db_name = "paddyguard"
    # Extract DB name from the URI if specified
    from urllib.parse import urlparse
    try:
        parsed = urlparse(uri)
        if parsed.path and parsed.path.strip("/"):
            db_name = parsed.path.strip("/")
    except Exception:
        pass
    return client[db_name]

class DocumentWrapper:
    def __init__(self, data=None):
        object.__setattr__(self, "_data", data or {})

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        return None

    def __setattr__(self, name, value):
        self._data[name] = value

    def __getitem__(self, key):
        return self._data.get(key)

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def to_dict(self):
        return self._data

