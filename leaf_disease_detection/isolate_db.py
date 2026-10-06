from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["paddyguard"]
res = db["prediction_cases"].update_many(
    {"review_status": "pending"},
    {"$set": {"review_status": "verified"}}
)
client.close()
print(f"Isolated DB. Updated {res.modified_count} cases.")
