"""
rss_news_collector.py — Collects health-related articles from RSS feeds
(Google News, DailyStar, ProthomAlo, BDNews24).

Uses shared base_collector for keywords, zone detection, dedup, and MongoDB save.
"""

import os
import sys
import feedparser
from datetime import datetime, timedelta
from time import mktime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collectors.base_collector import (
    is_health_related, save_post
)

# ─── RSS FEEDS ────────────────────────────────────────────────────────────────

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


def parse_date(entry):
    """Extract publish date from RSS entry — handles missing dates gracefully."""
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
    except Exception:
        pass
    return datetime.now()


def collect_rss_data(days_back=90):
    """
    Fetch all RSS feeds and save health-related articles to MongoDB.
    Uses base_collector.save_post() for dedup and zone detection.
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
                    title   = entry.get('title', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    text    = f"{title}. {summary}".strip()

                    if len(text) < 20:
                        feed_skipped += 1
                        continue
                    if not is_health_related(text):
                        feed_skipped += 1
                        continue

                    pub_date = parse_date(entry)
                    if pub_date < cutoff_date:
                        feed_skipped += 1
                        continue

                    # save_post() handles dedup, zone detection, and MongoDB insert
                    saved = save_post(
                        text=text,
                        platform="RSS_NEWS",
                        channel=source,
                        timestamp=pub_date,
                        source_url=entry.get('link', ''),
                    )

                    if saved:
                        feed_collected += 1
                        total_collected += 1
                    else:
                        feed_skipped += 1

                except Exception:
                    feed_skipped += 1
                    continue

            print(f"   ✅ {feed_collected} collected, {feed_skipped} skipped")
            total_skipped += feed_skipped

        except Exception as e:
            print(f"   ❌ Feed failed: {e}")
            total_failed += 1
            continue

    print(f"\n{'='*50}")
    print(f"✅ RSS COLLECTION COMPLETE")
    print(f"   New posts collected : {total_collected}")
    print(f"   Skipped             : {total_skipped}")
    print(f"   Failed feeds        : {total_failed}")

    from database import social_posts
    real_count = social_posts.count_documents({"simulated": False})
    print(f"   Total real posts in MongoDB: {real_count}")
    print(f"{'='*50}")

    return total_collected


if __name__ == "__main__":
    collect_rss_data(days_back=90)