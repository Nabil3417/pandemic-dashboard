import os
import sys
import feedparser
import hashlib
from datetime import datetime, timedelta
from time import mktime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import social_posts

# ─── RSS FEEDS ────────────────────────────────────────────────────────────────
# All free, no API key needed

RSS_FEEDS = [
    # English Bangladesh health/news
    {
        "url": "https://news.google.com/rss/search?q=bangladesh+health+outbreak+disease&hl=en-BD&gl=BD&ceid=BD:en",
        "source": "GoogleNews_EN_Health"
    },
    {
        "url": "https://news.google.com/rss/search?q=bangladesh+dengue+fever+hospital&hl=en-BD&gl=BD&ceid=BD:en",
        "source": "GoogleNews_EN_Dengue"
    },
    {
        "url": "https://news.google.com/rss/search?q=bangladesh+epidemic+virus+infection&hl=en-BD&gl=BD&ceid=BD:en",
        "source": "GoogleNews_EN_Epidemic"
    },
    {
        "url": "https://news.google.com/rss/search?q=dhaka+hospital+disease+outbreak&hl=en-BD&gl=BD&ceid=BD:en",
        "source": "GoogleNews_EN_Dhaka"
    },
    # Bangla health queries
    {
        "url": "https://news.google.com/rss/search?q=বাংলাদেশ+ডেঙ্গু+জ্বর&hl=bn&gl=BD&ceid=BD:bn",
        "source": "GoogleNews_BN_Dengue"
    },
    {
        "url": "https://news.google.com/rss/search?q=বাংলাদেশ+স্বাস্থ্য+রোগ+প্রাদুর্ভাব&hl=bn&gl=BD&ceid=BD:bn",
        "source": "GoogleNews_BN_Health"
    },
    {
        "url": "https://news.google.com/rss/search?q=ঢাকা+হাসপাতাল+সংক্রমণ&hl=bn&gl=BD&ceid=BD:bn",
        "source": "GoogleNews_BN_Dhaka"
    },
    # Direct news site RSS feeds
    {
        "url": "https://www.thedailystar.net/health/rss.xml",
        "source": "DailyStar_Health"
    },
    {
        "url": "https://www.thedailystar.net/rss.xml",
        "source": "DailyStar_General"
    },
    {
        "url": "https://www.prothomalo.com/feed",
        "source": "ProthomAlo"
    },
    {
        "url": "https://bdnews24.com/rss/bangla",
        "source": "BDNews24_Bangla"
    },
    {
        "url": "https://bdnews24.com/rss/health",
        "source": "BDNews24_Health"
    },
]

# ─── HEALTH KEYWORDS ──────────────────────────────────────────────────────────

HEALTH_KEYWORDS = [
    # English
    'fever', 'sick', 'hospital', 'flu', 'cough', 'outbreak', 'infection',
    'virus', 'symptom', 'medicine', 'doctor', 'clinic', 'patient', 'disease',
    'health', 'dengue', 'cholera', 'epidemic', 'pandemic', 'vaccination',
    'vaccine', 'WHO', 'DGHS', 'death toll', 'infected', 'pneumonia',
    'diarrhea', 'malaria', 'respiratory', 'iedcr', 'quarantine', 'mortality',
    'morbidity', 'pathogen', 'contagious', 'infectious',

    # Bangla
    'জ্বর', 'কাশি', 'হাসপাতাল', 'অসুস্থ', 'ডাক্তার', 'ভাইরাস', 'রোগ',
    'ঔষধ', 'সর্দি', 'ক্লিনিক', 'রোগী', 'স্বাস্থ্য', 'ইনফেকশন', 'করোনা',
    'ফ্লু', 'ডেঙ্গু', 'কলেরা', 'মহামারী', 'টিকা', 'আক্রান্ত', 'চিকিৎসা',
    'হাসপাতালে ভর্তি', 'সংক্রমণ', 'প্রাদুর্ভাব', 'নিউমোনিয়া', 'ডায়রিয়া',
    'ম্যালেরিয়া', 'শ্বাসকষ্ট', 'স্বাস্থ্যসেবা', 'চিকিৎসক', 'মৃত্যুহার',
    'রোগতত্ত্ব', 'আইইডিসিআর', 'স্বাস্থ্য অধিদপ্তর', 'স্বাস্থ্য মন্ত্রণালয়',
]

# ─── ZONE KEYWORDS ────────────────────────────────────────────────────────────

ZONE_KEYWORDS = {
    1:  ['uttara', 'উত্তরা', 'uttarkhan', 'dakshinkhan', 'khilkhet'],
    2:  ['mirpur', 'মিরপুর', 'pallabi', 'পল্লবী', 'rupnagar'],
    3:  ['gulshan', 'গুলশান', 'banani', 'বনানী', 'baridhara', 'mohakhali', 'tejgaon'],
    4:  ['agargaon', 'আগারগাঁও', 'kafrul', 'kazipara', 'shewrapara'],
    5:  ['farmgate', 'ফার্মগেট', 'karwan bazar', 'kawran', 'sher-e-bangla'],
    6:  ['diabari', 'দিয়াবাড়ি', 'ashkona', 'kawlar'],
    7:  ['uttarkhan', 'উত্তরখান', 'faidabad'],
    8:  ['dakshinkhan', 'দক্ষিণখান', 'dumni', 'satarkul'],
    9:  ['vatara', 'ভাটারা', 'kuril', 'কুড়িল', 'nurerchala'],
    10: ['badda', 'বাড্ডা', 'aftabnagar', 'beraid'],
    11: ['ramna', 'রমনা', 'motijheel', 'মতিঝিল', 'paltan', 'shahbagh', 'segunbagicha'],
    12: ['khilgaon', 'খিলগাঁও', 'mugda', 'basabo', 'malibagh', 'shantinagar'],
    13: ['dhanmondi', 'ধানমন্ডি', 'azimpur', 'lalbagh', 'hazaribagh', 'kalabagan'],
    14: ['wari', 'ওয়ারী', 'jatrabari', 'যাত্রাবাড়ী', 'sutrapur', 'gendaria', 'old dhaka'],
    15: ['bashundhara', 'বসুন্ধরা', 'nsu', 'north south university', 'নর্থ সাউথ'],
}

ZONE_COORDS = {
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

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def detect_zone(text):
    text_lower = text.lower()
    for zone_id, keywords in ZONE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return zone_id
    return 11  # Default to Motijheel/central Dhaka for general national news

def is_health_related(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in HEALTH_KEYWORDS)

def make_hash(text, source):
    """Create a unique hash for deduplication — avoids exact text comparison."""
    return hashlib.md5(f"{source}:{text[:100]}".encode()).hexdigest()

def already_exists(text_hash):
    return social_posts.find_one({"content_hash": text_hash}) is not None

def parse_date(entry):
    """Extract publish date from RSS entry — handles missing dates gracefully."""
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
    except Exception:
        pass
    return datetime.now()

# ─── MAIN COLLECTOR ───────────────────────────────────────────────────────────

def collect_rss_data(days_back=90):
    """
    Fetch all RSS feeds and save health-related articles to MongoDB.
    Runs in one pass — call from APScheduler every 6 hours.
    """
    print("🚀 Starting RSS News Collector")
    print(f"   Feeds: {len(RSS_FEEDS)}")
    print(f"   Looking back: {days_back} days")

    cutoff_date = datetime.now() - timedelta(days=days_back)
    total_collected = 0
    total_skipped   = 0
    total_failed    = 0

    for feed_config in RSS_FEEDS:
        url    = feed_config["url"]
        source = feed_config["source"]

        print(f"\n📡 Fetching: {source}")

        try:
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                print(f"   ⚠️  Could not parse feed (bozo error) — skipping")
                total_failed += 1
                continue

            feed_collected = 0
            feed_skipped   = 0

            for entry in feed.entries:
                try:
                    # Build full text from title + summary/description
                    title   = entry.get('title', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    text    = f"{title}. {summary}".strip()

                    # Skip very short entries
                    if len(text) < 20:
                        feed_skipped += 1
                        continue

                    # Skip if not health related
                    if not is_health_related(text):
                        feed_skipped += 1
                        continue

                    # Parse and check date
                    pub_date = parse_date(entry)
                    if pub_date < cutoff_date:
                        feed_skipped += 1
                        continue

                    # Deduplicate by hash
                    content_hash = make_hash(text, source)
                    if already_exists(content_hash):
                        feed_skipped += 1
                        continue

                    # Detect zone and get coords
                    zone_id = detect_zone(text)
                    zone    = ZONE_COORDS[zone_id]

                    # Build document
                    post = {
                        "text":          text,
                        "platform":      "RSS_NEWS",
                        "channel":       source,
                        "source_url":    entry.get('link', ''),
                        "timestamp":     pub_date,
                        "zone_id":       zone_id,
                        "location_name": zone["name"],
                        "latitude":      zone["lat"],
                        "longitude":     zone["lng"],
                        "processed":     False,
                        "bert_score":    None,
                        "simulated":     False,
                        "language":      "mixed",
                        "content_hash":  content_hash,
                    }

                    social_posts.insert_one(post)
                    feed_collected += 1
                    total_collected += 1

                except Exception as e:
                    feed_skipped += 1
                    continue

            print(f"   ✅ {feed_collected} collected, {feed_skipped} skipped")
            total_skipped += feed_skipped

        except Exception as e:
            print(f"   ❌ Feed failed: {e}")
            total_failed += 1
            continue

    # Final stats
    print(f"\n{'='*50}")
    print(f"✅ RSS COLLECTION COMPLETE")
    print(f"   New posts collected : {total_collected}")
    print(f"   Skipped             : {total_skipped}")
    print(f"   Failed feeds        : {total_failed}")
    real_count = social_posts.count_documents({"simulated": False})
    print(f"   Total real posts in MongoDB: {real_count}")
    print(f"{'='*50}")

    return total_collected


if __name__ == "__main__":
    collect_rss_data(days_back=90)