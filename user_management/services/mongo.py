"""One pooled Mongo client per process; explicit availability and safe audit logging."""
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4
from threading import Lock
from fastapi import HTTPException
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError, DuplicateKeyError

log = logging.getLogger(__name__)
client = None
_database = None
_indexed_database = None
_index_lock = Lock()


def initialize():
    global client, _database
    url = os.getenv("MONGO_URL")
    if not url:
        log.warning("MongoDB disabled: MONGO_URL is not configured")
        return
    try:
        client = MongoClient(url, maxPoolSize=20, serverSelectionTimeoutMS=2000,
                             connectTimeoutMS=2000, socketTimeoutMS=3000, waitQueueTimeoutMS=2000, tz_aware=True)
        _database = client[os.getenv("MONGO_DB_NAME", "paddyguard")]
        ensure_indexes(_database)
    except (PyMongoError, ValueError):
        log.warning("MongoDB configuration or index initialization unavailable; verify private configuration")


def ensure_indexes(db):
    global _indexed_database
    if _indexed_database is db:
        return
    if not _index_lock.acquire(timeout=2):
        raise HTTPException(503, "MongoDB storage unavailable")
    try:
        if _indexed_database is db:
            return
        db.feedback.create_index([("user_id", 1), ("created_at", DESCENDING)])
        db.feedback.create_index([("status", 1), ("consent_public", 1), ("rating", 1), ("created_at", DESCENDING)])
        db.activity_events.create_index([("user_id", 1), ("timestamp", DESCENDING)])
        db.activity_events.create_index([("timestamp", DESCENDING)])
        db.activity_events.create_index([("user_id", 1), ("event_type", 1), ("request_id", 1)], unique=True)
        db.profile_images.create_index("user_id", unique=True)
        _indexed_database = db
    finally:
        _index_lock.release()


def close():
    global client, _database, _indexed_database
    if client:
        client.close()
    client = _database = _indexed_database = None


def database():
    if _database is None:
        raise HTTPException(503, "MongoDB storage unavailable")
    ensure_indexes(_database)
    return _database



def record(user_id, event_type, module, request_id=None, metadata=None):
    # Only trusted callers supply enum event types and non-sensitive IDs/statuses.
    try:
        database().activity_events.insert_one({"_id": str(uuid4()), "user_id": user_id,
            "event_type": event_type, "module": module, "status": "SUCCESS",
            "timestamp": datetime.now(timezone.utc), "request_id": request_id or str(uuid4()),
            "metadata": metadata or {}})
    except DuplicateKeyError:
        pass
    except (PyMongoError, HTTPException):
        log.warning("Activity event could not be stored (event_type=%s)", event_type)
