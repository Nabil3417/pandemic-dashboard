import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto
from dotenv import load_dotenv
from database import social_posts

load_dotenv()

API_ID    = int(os.getenv('TELEGRAM_API_ID'))
API_HASH  = os.getenv('TELEGRAM_API_HASH')
PHONE     = os.getenv('TELEGRAM_PHONE')

# Public Bangladeshi health-related Telegram channels
# These are all public — no membership needed
CHANNELS = [
    'prothom_alo_feed',
    'TheDailyStar',
    'daily_jugantor',
    'somoynews_tv',
]
# Keywords that indicate health/illness content
HEALTH_KEYWORDS = [
    # English health terms
    'fever', 'sick', 'hospital', 'flu', 'cough', 'outbreak',
    'infection', 'virus', 'symptom', 'medicine', 'doctor',
    'clinic', 'patient', 'disease', 'health', 'ill', 'dengue',
    'cholera', 'epidemic', 'pandemic', 'vaccination', 'vaccine',
    'WHO', 'DGHS', 'ministry of health', 'death toll', 'infected',

    # Bangla health terms
    'জ্বর', 'কাশি', 'হাসপাতাল', 'অসুস্থ', 'ডাক্তার',
    'ভাইরাস', 'রোগ', 'ঔষধ', 'সর্দি', 'ক্লিনিক',
    'রোগী', 'স্বাস্থ্য', 'ইনফেকশন', 'করোনা', 'ফ্লু',
    'ডেঙ্গু', 'কলেরা', 'মহামারী', 'টিকা', 'মৃত্যু',
    'আক্রান্ত', 'চিকিৎসা', 'স্বাস্থ্য অধিদপ্তর',
    'হাসপাতালে ভর্তি', 'সংক্রমণ', 'প্রাদুর্ভাব',
    'স্বাস্থ্য মন্ত্রণালয়', 'রোগতত্ত্ব', 'শ্বাসকষ্ট',
    # Prothom Alo specific Bangla terms
'স্বাস্থ্যসেবা', 'চিকিৎসক', 'নিউমোনিয়া',
'হৃদরোগ', 'ক্যান্সার', 'ডায়াবেটিস', 'রক্ত',
'শিশু মৃত্যু', 'মাতৃমৃত্যু', 'পুষ্টি', 'সুস্বাস্থ্য',
'মেডিকেল', 'ওষুধ', 'চিকিৎসাসেবা', 'স্বাস্থ্যকর',
]

# Zone mapping based on keywords in message
ZONE_KEYWORDS = {
    1:  ['uttara', 'উত্তরা', 'uttarkhan', 'dakshinkhan', 'khilkhet',
         'উত্তরখান', 'দক্ষিণখান'],
    2:  ['mirpur', 'মিরপুর', 'pallabi', 'পল্লবী', 'rupnagar', 'রূপনগর'],
    3:  ['gulshan', 'গুলশান', 'banani', 'বনানী', 'baridhara', 'বারিধারা',
         'mohakhali', 'মহাখালী', 'tejgaon', 'তেজগাঁও'],
    4:  ['agargaon', 'আগারগাঁও', 'kafrul', 'কাফরুল', 'kazipara',
         'কাজীপাড়া', 'shewrapara', 'শেওড়াপাড়া'],
    5:  ['farmgate', 'ফার্মগেট', 'karwan bazar', 'কারওয়ান বাজার',
         'kawran', 'sher-e-bangla', 'শেরেবাংলা'],
    6:  ['diabari', 'দিয়াবাড়ি', 'ashkona', 'আশকোনা', 'kawlar'],
    7:  ['uttarkhan', 'উত্তরখান', 'faidabad', 'ফাইদাবাদ', 'barua', 'jamun'],
    8:  ['dakshinkhan', 'দক্ষিণখান', 'dumni', 'satarkul'],
    9:  ['vatara', 'ভাটারা', 'kuril', 'কুড়িল', 'nurerchala', 'নূরেরচালা'],
    10: ['badda', 'বাড্ডা', 'aftabnagar', 'আফতাবনগর', 'beraid'],
    11: ['ramna', 'রমনা', 'motijheel', 'মতিঝিল', 'paltan', 'পল্টন',
         'shahbagh', 'শাহবাগ', 'segunbagicha'],
    12: ['khilgaon', 'খিলগাঁও', 'mugda', 'মুগদা', 'basabo', 'বাসাবো',
         'malibagh', 'মালিবাগ', 'shantinagar', 'শান্তিনগর'],
    13: ['dhanmondi', 'ধানমন্ডি', 'azimpur', 'আজিমপুর', 'lalbagh',
         'লালবাগ', 'hazaribagh', 'হাজারীবাগ', 'kalabagan', 'কলাবাগান'],
    14: ['wari', 'ওয়ারী', 'jatrabari', 'যাত্রাবাড়ী', 'sutrapur',
         'সূত্রাপুর', 'gendaria', 'গেন্ডারিয়া', 'old dhaka', 'পুরান ঢাকা'],
    15: ['bashundhara', 'বসুন্ধরা', 'norda', 'নর্দা', 'nsu',
         'north south university', 'নর্থ সাউথ'],
}


def detect_zone(text):
    """Detect which zone a post belongs to based on location keywords."""
    text_lower = text.lower()
    for zone_id, keywords in ZONE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return zone_id
    return 15  # Default to NSU zone if no location match

def is_health_related(text):
    """Check if a message contains health-related keywords."""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in HEALTH_KEYWORDS)


def already_exists(text, platform):
    """Check if this post is already in MongoDB to avoid duplicates."""
    existing = social_posts.find_one({
        "text":     text,
        "platform": platform
    })
    return existing is not None


async def collect_from_channel(client, channel_username, days_back=30):
    """
    Collect messages from a single public Telegram channel.
    Returns count of posts collected.
    """
    collected = 0
    skipped   = 0
    errors    = 0

    try:
        print(f"\n📡 Connecting to channel: @{channel_username}")
        entity = await client.get_entity(channel_username)

        # Calculate date range
        date_from = datetime.now() - timedelta(days=days_back)

        async for message in client.iter_messages(
            entity,
            offset_date=datetime.now(),
            reverse=False,
            limit=500  # Max 500 messages per channel
        ):
            try:
                # Skip if no text
                if not message.text:
                    continue

                # Skip if too old
                if message.date.replace(tzinfo=None) < date_from:
                    break

                text = message.text.strip()

                # Skip very short messages
                if len(text) < 10:
                    continue

                # Skip if not health related
                if not is_health_related(text):
                    skipped += 1
                    continue

                # Skip duplicates
                if already_exists(text, 'Telegram'):
                    skipped += 1
                    continue

                # Detect zone
                zone_id = detect_zone(text)

                # Get zone location
                zone_coords = {
    1:  {"lat": 23.8759, "lng": 90.3795, "name": "Uttara"},
    2:  {"lat": 23.8223, "lng": 90.3654, "name": "Mirpur"},
    3:  {"lat": 23.7940, "lng": 90.4043, "name": "Gulshan & Banani"},
    4:  {"lat": 23.7751, "lng": 90.3668, "name": "Agargaon & Kafrul"},
    5:  {"lat": 23.7527, "lng": 90.3894, "name": "Farmgate & Karwan Bazar"},
    6:  {"lat": 23.9012, "lng": 90.3456, "name": "Diabari & Ashkona"},
    7:  {"lat": 23.9123, "lng": 90.4234, "name": "Uttarkhan & Faidabad"},
    8:  {"lat": 23.8934, "lng": 90.4456, "name": "Dakshinkhan & Dumni"},
    9:  {"lat": 23.8234, "lng": 90.4234, "name": "Vatara & Kuril"},
    10: {"lat": 23.7845, "lng": 90.4234, "name": "Badda & Aftabnagar"},
    11: {"lat": 23.7234, "lng": 90.4123, "name": "Ramna & Motijheel"},
    12: {"lat": 23.7345, "lng": 90.4345, "name": "Khilgaon & Mugda"},
    13: {"lat": 23.7456, "lng": 90.3789, "name": "Dhanmondi & Azimpur"},
    14: {"lat": 23.7123, "lng": 90.4234, "name": "Wari & Jatrabari"},
    15: {"lat": 23.8191, "lng": 90.4526, "name": "Bashundhara R/A (NSU)"},
}
                zone = zone_coords[zone_id]

                # Build post document
                post = {
                    "text":          text,
                    "platform":      "Telegram",
                    "channel":       channel_username,
                    "timestamp":     message.date.replace(tzinfo=None),
                    "zone_id":       zone_id,
                    "location_name": zone["name"],
                    "latitude":      zone["lat"],
                    "longitude":     zone["lng"],
                    "processed":     False,
                    "bert_score":    None,
                    "simulated":     False,   # REAL DATA
                    "language":      "mixed"  # Bangla/English/Banglish
                }

                social_posts.insert_one(post)
                collected += 1

                if collected % 10 == 0:
                    print(f"   ✅ Collected {collected} posts from @{channel_username}")

            except Exception as e:
                errors += 1
                continue

        print(f"   📊 @{channel_username}: {collected} collected, "
              f"{skipped} skipped, {errors} errors")
        return collected

    except Exception as e:
        print(f"   ❌ Could not access @{channel_username}: {e}")
        return 0


async def run_collector(days_back=30):
    """Main function — connects to Telegram and collects from all channels."""

    print("🚀 Starting Telegram Health Data Collector")
    print(f"   Collecting last {days_back} days of messages")
    print(f"   Target channels: {len(CHANNELS)}")
    print(f"   Health keywords: {len(HEALTH_KEYWORDS)}")

    # Create Telegram client
    # Session file saved locally so you only need to log in once
    client = TelegramClient('bioguard_session', API_ID, API_HASH)

    await client.start(phone=PHONE)
    print("\n✅ Telegram client connected!")

    total_collected = 0

    for channel in CHANNELS:
        count = await collect_from_channel(client, channel, days_back)
        total_collected += count

    await client.disconnect()

    # Print final stats
    print(f"\n{'='*50}")
    print(f"✅ COLLECTION COMPLETE")
    print(f"   Total posts collected: {total_collected}")

    # Check MongoDB stats
    real_count = social_posts.count_documents({"simulated": False})
    print(f"   Total real posts in MongoDB: {real_count}")
    print(f"{'='*50}")

    return total_collected


def collect_telegram_data(days_back=30):
    """Synchronous wrapper — call this from app.py or APScheduler."""
    return asyncio.run(run_collector(days_back))


if __name__ == "__main__":
    collect_telegram_data(days_back=30)