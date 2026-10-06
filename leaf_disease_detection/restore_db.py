from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["paddyguard"]
res = db["prediction_cases"].update_many(
    {"review_status": "verified", "verified_at": None},
    {"$set": {"review_status": "pending"}}
)
client.close()
print(f"Restored DB. Updated {res.modified_count} cases.")
