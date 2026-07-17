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


# Zone definitions — loaded from zones.json (single source of truth)
from zones_loader import ZONE_KEYWORDS, ZONE_COORDS

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