import os
"""Quick diagnostic to check actual data structures in MongoDB and zones.json."""
import json
from pymongo import MongoClient
from pathlib import Path

# MongoDB
client = MongoClient(
    os.getenv("MONGO_URI", ""),
    serverSelectionTimeoutMS=10000
)
db = client["bioguard_research"]

# 1) Check zones.json structure
print("=" * 60)
print("1) zones.json structure")
print("=" * 60)
with open("data/zones.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"  Top-level keys: {list(data.keys())}")
print(f"  zones type: {type(data['zones'])}")
if isinstance(data["zones"], dict):
    first_key = list(data["zones"].keys())[0]
    print(f"  First key: {first_key}")
    print(f"  First value: {data['zones'][first_key]}")
elif isinstance(data["zones"], list):
    print(f"  First zone: {data['zones'][0]}")

# 2) Check each collection
collections = [
    "google_mobility_data",
    "social_volume_data",
    "osrm_routing_data",
    "google_trends_signal",
]

print("\n" + "=" * 60)
print("2) MongoDB collection samples")
print("=" * 60)

for coll_name in collections:
    print(f"\n  --- {coll_name} ---")
    count = db[coll_name].count_documents({})
    print(f"  Total docs: {count}")
    if count > 0:
        sample = db[coll_name].find_one({}, {"_id": 0})
        print(f"  Sample doc keys: {list(sample.keys())}")
        print(f"  Sample doc: {sample}")

client.close()