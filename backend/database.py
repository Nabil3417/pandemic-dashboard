from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import os
import certifi
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')

try:
    client = MongoClient(
        MONGO_URI,
        server_api=ServerApi('1'),
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True,
        tlsAllowInvalidHostnames=True
    )
    client.admin.command('ping')
    print("✅ Connected to MongoDB Atlas!")
    db = client['bioguard_research']

except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit(1)

# Collections
social_posts        = db['social_media_posts']
mobility_data       = db['mobility_events']
wastewater_readings = db['wastewater_readings']
risk_snapshots      = db['risk_snapshots']      # NEW — stores every prediction result
zones_collection    = db['zones']               # NEW — stores zone definitions
trends_data         = db['trends_data']         # NEW — real Google Trends symptom-search data


def save_risk_snapshot(zone_id, city, nlp_score, mobility_anomaly,
                       wastewater_score, fused_score, risk_level,
                       cluster_size=0, mobility_score=0):
    risk_snapshots.insert_one({
        "zone_id":          zone_id,
        "city":             city,
        "nlp_score":        nlp_score,
        "mobility_anomaly": mobility_anomaly,
        "mobility_score":   mobility_score,
        "cluster_size":     cluster_size,
        "wastewater_score": wastewater_score,
        "fused_score":      fused_score,
        "risk_level":       risk_level,
        "timestamp":        datetime.now()
    })


def get_unprocessed_posts(limit=20):
    """
    Returns posts that haven't been scored by BERT yet.
    """
    return list(social_posts.find(
        {"bert_score": None, "simulated": True},
        limit=limit
    ))


def update_post_bert_score(post_id, score):
    """
    Writes BERT score back to the post document in MongoDB.
    """
    social_posts.update_one(
        {"_id": post_id},
        {"$set": {"bert_score": score, "processed": True}}
    )


def get_recent_posts_by_zone(zone_id, limit=5):
    """
    Returns the most recent posts for a specific zone.
    """
    return list(social_posts.find(
        {"zone_id": zone_id},
        sort=[("timestamp", -1)],
        limit=limit
    ))


def get_zone_avg_bert_score(zone_id):
    """
    Returns average BERT score for a zone from recently processed posts.
    Falls back to None if no processed posts exist yet.
    """
    pipeline = [
        {"$match": {"zone_id": zone_id, "bert_score": {"$ne": None}}},
        {"$group": {"_id": "$zone_id", "avg_score": {"$avg": "$bert_score"}}}
    ]
    result = list(social_posts.aggregate(pipeline))
    return result[0]['avg_score'] if result else None


def save_trends_snapshot(zone_id, zone_name, date, symptom_score, source="google_trends"):
    """
    Saves one zone-week Google Trends symptom-search record.
    Upserts on (zone_id, date) so re-running the collector doesn't
    create duplicate rows for a week that was already collected.
    """
    trends_data.update_one(
        {"zone_id": zone_id, "date": date},
        {"$set": {
            "zone_id":       zone_id,
            "zone_name":     zone_name,
            "date":          date,
            "symptom_score": symptom_score,
            "source":        source,
            "collected_at":  datetime.now(),
        }},
        upsert=True
    )


def get_zone_trends_series(zone_id, limit=100):
    """
    Returns the stored Google Trends time series for a zone, sorted
    oldest -> newest. Used by engine_wastewater.py to fit ARIMA on
    REAL data instead of the synthetic fallback series.
    """
    docs = list(trends_data.find(
        {"zone_id": zone_id},
        sort=[("date", 1)],
        limit=limit
    ))
    return docs


def get_latest_zone_trends_score(zone_id):
    """
    Returns the most recent real symptom-search score for a zone,
    or None if no Google Trends data has been collected yet for it.
    """
    doc = trends_data.find_one(
        {"zone_id": zone_id},
        sort=[("date", -1)]
    )
    return doc['symptom_score'] if doc else None


def get_trends_data_stats():
    """Returns collection stats — used by /api/db-stats to show real vs missing coverage."""
    total = trends_data.count_documents({})
    zones_with_data = len(trends_data.distinct("zone_id"))
    latest = trends_data.find_one(sort=[("date", -1)])
    return {
        "total_trends_records": total,
        "zones_with_real_data": zones_with_data,
        "latest_date": latest['date'] if latest else None,
    }


def test_connection():
    try:
        result = social_posts.insert_one({
            "text":      "Test post from MongoDB Atlas",
            "timestamp": datetime.now(),
            "processed": False,
            "test":      True
        })
        print("✅ MongoDB Atlas connected successfully!")
        print(f"   Document ID: {result.inserted_id}")
        social_posts.delete_many({"test": True})
        print("✅ Test data cleaned up!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")


if __name__ == "__main__":
    test_connection()