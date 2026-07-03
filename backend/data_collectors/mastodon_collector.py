"""
mastodon_collector.py — Collects health-related public posts from Mastodon
instances using hashtag timelines (no auth required).

Strategy:
  1. Fetch recent posts from health-related hashtags on multiple instances
  2. Filter for Bangladesh/Dhaka relevance + health keywords
  3. Auto-detect Dhaka zone from post text
  4. Save to MongoDB via base_collector.save_post()

No API key needed — uses public hashtag timeline endpoints.
"""

import os
import sys
import re
import requests
import time
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collectors.base_collector import is_health_related, save_post


# ─── CONFIG ────────────────────────────────────────────────────────────────────

# Mastodon instances to search (large, public-timeline-friendly)
MASTODON_INSTANCES = [
    "mastodon.social",
    "mstdn.social",
    "mastodon.online",
    "mastodon.world",
    "social.vivaldi.net",
    "masto.ai",
    
]

# Hashtags to follow (no # prefix)
HASHTAGS = [
    "dengue",
    "bangladesh",
    "dhaka",
    "outbreak",
    "epidemic",
    "pandemic",
    "publichealth",
    "health",
    "hospital",
    "fever",
    "disease",
    "cholera",
    "virus",
    "infection",
    "WHO",
]

# Extra keywords to filter for Bangladesh/Dhaka relevance
BANGLADESH_FILTERS = [
    "bangladesh", "বাংলাদেশ", "dhaka", "ঢাকা", "dengue", "ডেঙ্গু",
]

MAX_PER_TAG = 40
DAYS_BACK = 90
REQUEST_DELAY = 1.0


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def clean_text(text):
    """Remove HTML tags, URLs, and clean up text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_timestamp(ts_string):
    """Convert Mastodon ISO timestamp to naive datetime."""
    try:
        dt = datetime.fromisoformat(ts_string.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except Exception:
        return datetime.now()


def fetch_hashtag_timeline(instance, hashtag, max_results=MAX_PER_TAG):
    """Fetch recent posts from a hashtag timeline on a Mastodon instance."""
    base_url = f"https://{instance}"
    results = []

    try:
        resp = requests.get(
            f"{base_url}/api/v1/timelines/tag/{hashtag}",
            params={"limit": max_results},
            headers={"User-Agent": "BioGuardAI/1.0 (Research Project)"},
            timeout=15,
        )

        if resp.status_code == 404:
            return results  # Tag doesn't exist on this instance
        if resp.status_code == 403:
            return results  # Blocked
        if resp.status_code != 200:
            print(f"      ⚠️  {instance} #{hashtag}: HTTP {resp.status_code}")
            return results

        for status in resp.json():
            text = clean_text(status.get("content", ""))
            if len(text) < 15:
                continue

            account = status.get("account", {})
            results.append({
                "text": text,
                "author": f"@{account.get('acct', 'unknown')}",
                "instance": instance,
                "created_at": status.get("created_at", ""),
                "url": status.get("url", ""),
                "like_count": status.get("favourites_count", 0),
                "reblog_count": status.get("reblogs_count", 0),
            })

    except requests.exceptions.Timeout:
        print(f"      ⏱️  Timeout on {instance}")
    except requests.exceptions.ConnectionError:
        print(f"      🔌 Connection failed for {instance}")
    except Exception as e:
        print(f"      ⚠️  Error on {instance} #{hashtag}: {e}")

    return results


# ─── MAIN COLLECTOR ────────────────────────────────────────────────────────────

def collect_mastodon_data(days_back=DAYS_BACK):
    """
    Fetch health-related hashtag timelines from Mastodon instances,
    filter for Bangladesh relevance, and save to MongoDB.
    """
    print("🚀 Starting Mastodon Collector")
    print(f"   Instances: {len(MASTODON_INSTANCES)}")
    print(f"   Hashtags : {len(HASHTAGS)}")
    print(f"   Looking back: {days_back} days")

    cutoff_date = datetime.now() - timedelta(days=days_back)

    total_collected = 0
    total_skipped = 0
    total_checked = 0

    for hashtag in HASHTAGS:
        print(f"\n🏷️  Fetching #{hashtag}")

        for instance in MASTODON_INSTANCES:
            results = fetch_hashtag_timeline(instance, hashtag)
            tag_saved = 0

            for toot in results:
                total_checked += 1
                text = toot["text"]
                text_lower = text.lower()

                # Must mention Bangladesh/Dhaka OR be specifically about dengue
                if not any(filt in text_lower for filt in BANGLADESH_FILTERS):
                    total_skipped += 1
                    continue

                # Must also have health keywords
                if not is_health_related(text):
                    total_skipped += 1
                    continue

                # Parse timestamp
                ts = parse_timestamp(toot["created_at"])
                if ts < cutoff_date:
                    total_skipped += 1
                    continue

                # Save via base_collector
                saved = save_post(
                    text=text,
                    platform="Mastodon",
                    channel=f"{toot['instance']}/{toot['author']}",
                    timestamp=ts,
                    source_url=toot["url"],
                    extra_fields={
                        "mastodon_instance": toot["instance"],
                        "author_handle": toot["author"],
                        "hashtag": hashtag,
                        "like_count": toot["like_count"],
                        "reblog_count": toot["reblog_count"],
                    }
                )

                if saved:
                    tag_saved += 1
                    total_collected += 1
                else:
                    total_skipped += 1

            if tag_saved > 0:
                print(f"   ✅ {instance} #{hashtag}: {tag_saved} saved")

            # Rate limiting
            time.sleep(REQUEST_DELAY)

    # Final stats
    print(f"\n{'='*50}")
    print(f"✅ MASTODON COLLECTION COMPLETE")
    print(f"   Posts checked    : {total_checked}")
    print(f"   Posts collected  : {total_collected}")
    print(f"   Posts skipped    : {total_skipped}")
    print(f"{'='*50}")

    return total_collected


if __name__ == "__main__":
    collect_mastodon_data(days_back=90)