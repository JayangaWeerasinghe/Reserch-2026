"""Explicit opt-in TTL setup. May expire OLD events immediately; back up first."""
import argparse
import os
from dotenv import load_dotenv
load_dotenv()
from services import mongo

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--confirm-expire-existing-events', action='store_true')
    args = parser.parse_args()
    days = int(os.getenv('ACTIVITY_RETENTION_DAYS', '0'))
    if not args.confirm_expire_existing_events or days < 1:
        parser.error('Set ACTIVITY_RETENTION_DAYS >= 1 and explicitly confirm expiration of existing events')
    mongo.initialize()
    try:
        db = mongo.database()
        indexes = db.activity_events.index_information()
        if 'activity_retention' in indexes:
            db.command({'collMod': 'activity_events', 'index': {'name': 'activity_retention', 'expireAfterSeconds': days * 86400}})
        else:
            db.activity_events.create_index('timestamp', name='activity_retention', expireAfterSeconds=days * 86400)
        print('Activity retention configured')
    finally:
        mongo.close()
