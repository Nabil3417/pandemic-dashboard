"""
bluesky_collector.py — Collects health-related public posts from Bluesky
(AT Protocol / bsky.social).

Strategy:
  1. Search Bluesky for health-related posts about Bangladesh
  2. Filter by health keywords
  3. Auto-detect Dhaka zone from post text
  4. Save to MongoDB via base_collector.save_post()

No API key required for public search (rate-limited to ~1000 req/day).
"""

import os
import sys
import re
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atproto import Client
from atproto.exceptions import AtProtocolError

from data_collectors.base_collector import is_health_related, save_post


# ─── CONFIG ────────────────────────────────────────────────────────────────────

SEARCH_QUERIES = [
    "bangladesh dengue",
    "bangladesh hospital",
    "bangladesh fever outbreak",
    "bangladesh disease",
    "bangladesh health",
    "dhaka hospital",
    "dhaka dengue",
    "bangladesh epidemic",
    "bangladesh virus",
    "বাংলাদেশ ডেঙ্গু",
    "বাংলাদেশ স্বাস্থ্য",
    "ঢাকা হাসপাতাল",
    "বাংলাদেশ প্রাদুর্ভাব",
]

MAX_RESULTS_PER_QUERY = 50
DAYS_BACK = 90


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def clean_text(text):
    """Remove URLs and clean up post text."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_bluesky_timestamp(ts_string):
    """Convert Bluesky ISO timestamp to naive datetime."""
    try:
        # Bluesky timestamps look like "2025-01-15T10:30:00.000Z"
        dt = datetime.fromisoformat(ts_string.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except Exception:
        return datetime.now()


# ─── MAIN COLLECTOR ────────────────────────────────────────────────────────────

def collect_bluesky_data(days_back=DAYS_BACK):
    """
    Search Bluesky for health-related posts about Bangladesh
    and save them to MongoDB.
    """
    print("🚀 Starting Bluesky Collector")
    print(f"   Queries: {len(SEARCH_QUERIES)}")
    print(f"   Looking back: {days_back} days")

    cutoff_date = datetime.now() - timedelta(days=days_back)

    # Create client and authenticate
    handle = os.getenv("BLUESKY_HANDLE", "")
    password = os.getenv("BLUESKY_APP_PASSWORD", "")

    if not handle or not password:
        print("   ❌ BLUESKY_HANDLE and BLUESKY_APP_PASSWORD not set in .env!")
        print("   Get a free account at https://bsky.social")
        print("   Create app password at https://bsky.app/settings/app-passwords")
        return 0

    client = Client()
    try:
        client.login(handle, password)
        print(f"   ✅ Authenticated as @{handle}")
    except Exception as e:
        print(f"   ❌ Login failed: {e}")
        return 0

    total_collected = 0
    total_skipped = 0
    total_errors = 0

    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")

        try:
            response = client.app.bsky.feed.search_posts({
                "q": query,
                "limit": MAX_RESULTS_PER_QUERY,
                "sort": "latest",
            })

            posts = response.posts if hasattr(response, 'posts') else []
            query_saved = 0

            for post in posts:
                try:
                    # Get text from post record
                    text = clean_text(post.record.text)

                    if len(text) < 15:
                        total_skipped += 1
                        continue

                    # Health keyword filter
                    if not is_health_related(text):
                        total_skipped += 1
                        continue

                    # Parse timestamp
                    ts = parse_bluesky_timestamp(post.record.created_at)

                    if ts < cutoff_date:
                        total_skipped += 1
                        continue

                    # Author info
                    author_handle = post.author.handle if post.author else "unknown"

                    # Save via base_collector
                    saved = save_post(
                        text=text,
                        platform="Bluesky",
                        channel=author_handle,
                        timestamp=ts,
                        source_url=f"https://bsky.app/profile/{author_handle}/post/{post.cid[:10]}",
                        extra_fields={
                            "bluesky_cid": str(post.cid),
                            "author_handle": author_handle,
                            "like_count": post.like_count if hasattr(post, 'like_count') else 0,
                            "repost_count": post.repost_count if hasattr(post, 'repost_count') else 0,
                        }
                    )

                    if saved:
                        query_saved += 1
                        total_collected += 1
                    else:
                        total_skipped += 1

                except Exception as e:
                    total_skipped += 1
                    continue

            print(f"   ✅ {query_saved} saved from this query")

        except AtProtocolError as e:
            print(f"   ⚠️  API error: {e}")
            total_errors += 1
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
            total_errors += 1

    # Final stats
    print(f"\n{'='*50}")
    print(f"✅ BLUESKY COLLECTION COMPLETE")
    print(f"   Posts collected : {total_collected}")
    print(f"   Posts skipped   : {total_skipped}")
    print(f"   Query errors    : {total_errors}")
    print(f"{'='*50}")

    return total_collected


if __name__ == "__main__":
    collect_bluesky_data(days_back=90)