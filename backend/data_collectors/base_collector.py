"""
base_collector.py — Shared utilities for ALL BioGuard data collectors.

Every collector (Telegram, RSS, YouTube, Bluesky, Mastodon) imports from here
instead of duplicating zone/keyword/dedup logic.

Usage in any collector:
    from base_collector import (
        HEALTH_KEYWORDS, ZONE_KEYWORDS, ZONE_COORDS,
        detect_zone, is_health_related, make_hash,
        already_exists, save_post, ZONE_DEFAULT
    )
"""

import hashlib
import sys
import os
from datetime import datetime

# ─── Ensure database.py is importable ──────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import social_posts


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH KEYWORDS — merged from Telegram + RSS collectors
# ══════════════════════════════════════════════════════════════════════════════

HEALTH_KEYWORDS = [
    # ── English ──────────────────────────────────────────────
    'fever', 'sick', 'hospital', 'flu', 'cough', 'outbreak',
    'infection', 'virus', 'symptom', 'medicine', 'doctor',
    'clinic', 'patient', 'disease', 'health', 'ill', 'dengue',
    'cholera', 'epidemic', 'pandemic', 'vaccination', 'vaccine',
    'WHO', 'DGHS', 'ministry of health', 'death toll', 'infected',
    'pneumonia', 'diarrhea', 'malaria', 'respiratory', 'iedcr',
    'quarantine', 'mortality', 'morbidity', 'pathogen', 'contagious',
    'infectious', 'case count', 'admitted', 'icu', 'emergency',

    # ── Bangla ──────────────────────────────────────────────
    'জ্বর', 'কাশি', 'হাসপাতাল', 'অসুস্থ', 'ডাক্তার',
    'ভাইরাস', 'রোগ', 'ঔষধ', 'সর্দি', 'ক্লিনিক',
    'রোগী', 'স্বাস্থ্য', 'ইনফেকশন', 'করোনা', 'ফ্লু',
    'ডেঙ্গু', 'কলেরা', 'মহামারী', 'টিকা', 'মৃত্যু',
    'আক্রান্ত', 'চিকিৎসা', 'স্বাস্থ্য অধিদপ্তর',
    'হাসপাতালে ভর্তি', 'সংক্রমণ', 'প্রাদুর্ভাব',
    'স্বাস্থ্য মন্ত্রণালয়', 'রোগতত্ত্ব', 'শ্বাসকষ্ট',
    'স্বাস্থ্যসেবা', 'চিকিৎসক', 'নিউমোনিয়া',
    'হৃদরোগ', 'ক্যান্সার', 'ডায়াবেটিস', 'রক্ত',
    'শিশু মৃত্যু', 'মাতৃমৃত্যু', 'পুষ্টি', 'সুস্বাস্থ্য',
    'মেডিকেল', 'ওষুধ', 'চিকিৎসাসেবা', 'স্বাস্থ্যকর',
    'ডায়রিয়া', 'ম্যালেরিয়া', 'মৃত্যুহার',
    'আইইডিসিআর', 'আইসিইউ', 'জরুরি',
]


# ══════════════════════════════════════════════════════════════════════════════
# ZONE DEFINITIONS — 15 Dhaka monitoring zones
# ══════════════════════════════════════════════════════════════════════════════

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
    8:  ['dakshinkhan', 'দক্ষিনখান', 'dumni', 'satarkul'],
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

# Default zone when no location keyword matches
ZONE_DEFAULT = 15  # NSU / Bashundhara research zone


# ══════════════════════════════════════════════════════════════════════════════
# CORE HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def detect_zone(text, default=ZONE_DEFAULT):
    """Detect which zone a post belongs to based on location keywords."""
    text_lower = text.lower()
    for zone_id, keywords in ZONE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return zone_id
    return default


def is_health_related(text):
    """Check if text contains any health-related keyword (Bangla or English)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in HEALTH_KEYWORDS)


def make_hash(text, source, length=100):
    """
    Create a unique MD5 hash for deduplication.
    Uses first `length` chars of text + source to avoid exact-match issues.
    """
    return hashlib.md5(f"{source}:{text[:length]}".encode()).hexdigest()


def already_exists(content_hash, text=None, platform=None):
    """Check if a post already exists — by hash first, then text+platform fallback."""
    # Primary: hash match
    existing = social_posts.find_one({"content_hash": content_hash})
    if existing:
        return True

    # Fallback: exact text + platform match (for old posts without content_hash)
    if text and platform:
        existing = social_posts.find_one({"text": text, "platform": platform})
        if existing:
            return True

    return False

def save_post(text, platform, channel, timestamp, zone_id=None,
              source_url=None, extra_fields=None):
    """
    Save a post to the social_media_posts collection.

    Parameters:
        text          (str)      — Post text content
        platform      (str)      — e.g. "Telegram", "RSS_NEWS", "YouTube", "Bluesky", "Mastodon"
        channel       (str)      — Source identifier (channel name, feed name, video ID, etc.)
        timestamp     (datetime) — Post publish/creation time
        zone_id       (int|None) — If None, auto-detected from text
        source_url    (str|None) — Original URL (if available)
        extra_fields  (dict|None)— Any platform-specific fields (e.g. view_count, likes)

    Returns:
        bool — True if saved, False if duplicate
    """
    # Auto-detect zone if not provided
    if zone_id is None:
        zone_id = detect_zone(text)

    zone = ZONE_COORDS[zone_id]

    # Dedup: hash + text+platform fallback
    content_hash = make_hash(text, platform)

    if already_exists(content_hash, text=text, platform=platform):
        return False

    # Build standard post document
    post = {
        "text":          text,
        "platform":      platform,
        "channel":       channel,
        "timestamp":     timestamp,
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

    # Add optional fields
    if source_url:
        post["source_url"] = source_url
    if extra_fields:
        post.update(extra_fields)

    social_posts.insert_one(post)
    return True