from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import os
import ssl
import certifi
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')

# Create a custom SSL context that works with OpenSSL 3.0.x on Windows
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

try:
    client = MongoClient(
        MONGO_URI,
        server_api=ServerApi('1'),
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True,
        tlsAllowInvalidHostnames=True,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
        socketTimeoutMS=30000,
    )
    client.admin.command('ping')
    print("✅ Connected to MongoDB Atlas!")
    db = client['bioguard_research']

except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit(1)

social_posts    = db['social_media_posts']
mobility_data   = db['mobility_events']
wastewater_readings = db['wastewater_readings']

def test_connection():
    try:
        result = social_posts.insert_one({
            "text": "Test post from MongoDB Atlas",
            "timestamp": datetime.now(),
            "processed": False,
            "test": True
        })
        print("✅ Test document inserted!")
        print(f"   Document ID: {result.inserted_id}")
        social_posts.delete_many({"test": True})
        print("✅ Test data cleaned up!")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_connection()