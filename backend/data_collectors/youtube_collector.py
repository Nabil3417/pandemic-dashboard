"""
youtube_collector.py — Collects health-related YouTube comments
about Bangladesh disease outbreaks.

Strategy:
  1. Search YouTube for health-related videos (Bangla + English queries)
  2. Fetch top comments from each video
  3. Filter comments by health keywords
  4. Auto-detect Dhaka zone from comment text
  5. Save to MongoDB via base_collector.save_post()
"""

import os
import sys
import re
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from data_collectors.base_collector import (
    is_health_related, save_post
)

# ─── CONFIG ────────────────────────────────────────────────────────────────────

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Search queries — mix of Bangla and English health terms for Bangladesh
SEARCH_QUERIES = [
    "bangladesh dengue 2024",
    "bangladesh dengue 2025",
    "bangladesh hospital outbreak",
    "bangladesh disease fever",
    "bangladesh health crisis",
    "ঢাকা ডেঙ্গু",
    "বাংলাদেশ ডেঙ্গু জ্বর",
    "বাংলাদেশ হাসপাতাল রোগী",
    "বাংলাদেশ স্বাস্থ্য প্রাদুর্ভাব",
    "ঢাকা মহামারী",
    "bangladesh cholera",
    "bangladesh flu outbreak",
    "dhaka hospital emergency",
    "bangladesh virus infection",
]

# How many videos to check per query
MAX_VIDEOS_PER_QUERY = 5
# How many comments to fetch per video
MAX_COMMENTS_PER_VIDEO = 50
# Only collect comments from the last N days
DAYS_BACK = 90


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def clean_comment_text(text):
    """Remove URLs, extra whitespace, and emoji artifacts from comment text."""
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def search_videos(youtube, query, max_results=MAX_VIDEOS_PER_QUERY):
    """Search YouTube and return video IDs for a given query."""
    try:
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            order="relevance",
            publishedAfter=(
                datetime.now() - timedelta(days=DAYS_BACK)
           ).isoformat("T") + "Z"  # noqa — cutoff date
        )
        response = request.execute()

        video_ids = []
        for item in response.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)

        return video_ids

    except HttpError as e:
        print(f"   ⚠️  Search error for '{query}': {e}")
        return []


def get_video_comments(youtube, video_id, max_results=MAX_COMMENTS_PER_VIDEO):
    """Fetch comments for a single video. Returns list of comment dicts."""
    comments = []
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance",
            textFormat="plainText"
        )
        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = clean_comment_text(snippet["textDisplay"])

            if len(text) < 15:
                continue

            comments.append({
                "text": text,
                "author": snippet.get("authorDisplayName", ""),
                "video_id": video_id,
                "like_count": snippet.get("likeCount", 0),
                "published_at": snippet.get("publishedAt", ""),
            })

    except HttpError as e:
        if e.resp.status == 403:
            print(f"   ⚠️  Comments disabled for video {video_id}")
        else:
            print(f"   ⚠️  Comment fetch error: {e}")

    return comments


# ─── MAIN COLLECTOR ────────────────────────────────────────────────────────────

def collect_youtube_data(days_back=DAYS_BACK):
    """
    Search YouTube for health-related Bangladesh videos,
    then collect and store relevant comments to MongoDB.
    """
    print("🚀 Starting YouTube Comments Collector")
    print(f"   Queries: {len(SEARCH_QUERIES)}")
    print(f"   Looking back: {days_back} days")

    if not YOUTUBE_API_KEY:
        print("   ❌ YOUTUBE_API_KEY not found in .env!")
        return 0

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    cutoff_date = datetime.now() - timedelta(days=days_back)
    total_collected = 0
    total_skipped = 0
    videos_checked = 0

    # Collect all unique video IDs across all queries
    all_video_ids = set()

    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")
        vid_ids = search_videos(youtube, query)
        all_video_ids.update(vid_ids)
        print(f"   Found {len(vid_ids)} videos")

    print(f"\n📋 Total unique videos to check: {len(all_video_ids)}")

    # Fetch comments from each video
    for video_id in all_video_ids:
        videos_checked += 1
        comments = get_video_comments(youtube, video_id)

        video_saved = 0
        for comment in comments:
            text = comment["text"]

            # Health keyword filter
            if not is_health_related(text):
                total_skipped += 1
                continue

            # Parse YouTube timestamp to datetime
            try:
                ts = datetime.fromisoformat(
                    comment["published_at"].replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                ts = datetime.now()

            # Skip if older than cutoff
            if ts < cutoff_date:
                total_skipped += 1
                continue

            # Save via base_collector
            saved = save_post(
                text=text,
                platform="YouTube",
                channel=video_id,
                timestamp=ts,
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                extra_fields={
                    "video_id": video_id,
                    "comment_author": comment["author"],
                    "like_count": comment["like_count"],
                }
            )

            if saved:
                video_saved += 1
                total_collected += 1
            else:
                total_skipped += 1

        if video_saved > 0:
            print(f"   ✅ Video {video_id}: {video_saved} comments saved")

    # Final stats
    print(f"\n{'='*50}")
    print(f"✅ YOUTUBE COLLECTION COMPLETE")
    print(f"   Videos checked     : {videos_checked}")
    print(f"   Comments collected : {total_collected}")
    print(f"   Comments skipped   : {total_skipped}")
    print(f"{'='*50}")

    return total_collected


if __name__ == "__main__":
    collect_youtube_data(days_back=90)