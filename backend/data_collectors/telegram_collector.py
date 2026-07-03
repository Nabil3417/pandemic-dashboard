"""
telegram_collector.py — Collects health-related posts from public
Bangladeshi Telegram channels.

Uses shared base_collector for keywords, zone detection, dedup, and MongoDB save.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from dotenv import load_dotenv
load_dotenv()

from data_collectors.base_collector import (
    is_health_related, detect_zone, save_post
)

API_ID   = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
PHONE    = os.getenv('TELEGRAM_PHONE')

# Public Bangladeshi health-related Telegram channels
CHANNELS = [
    'Conflict_Watch_Bangla',
    'JamunaTelevisionOfficial',
    'channelelias',
    'basherkella',
    'newsboxbangla',
    'internationalnews007',
    'ShamsulArefin2091',
    'drsalimaldeen',
    'prothom_alo_feed',
    'TheDailyStar',
    'daily_jugantor',
    'somoynews_tv',
]


async def collect_from_channel(client, channel_username, days_back=30):
    """Collect health-related messages from a single public Telegram channel."""
    collected = 0
    skipped   = 0
    errors    = 0

    try:
        print(f"\n📡 Connecting to channel: @{channel_username}")
        entity = await client.get_entity(channel_username)

        date_from = datetime.now() - timedelta(days=days_back)

        async for message in client.iter_messages(
            entity,
            offset_date=datetime.now(),
            reverse=False,
            limit=500
        ):
            try:
                if not message.text:
                    continue
                if message.date.replace(tzinfo=None) < date_from:
                    break

                text = message.text.strip()
                if len(text) < 10:
                    continue
                if not is_health_related(text):
                    skipped += 1
                    continue

                # save_post() handles dedup, zone detection, and MongoDB insert
                saved = save_post(
                    text=text,
                    platform="Telegram",
                    channel=channel_username,
                    timestamp=message.date.replace(tzinfo=None),
                    extra_fields={
                        "message_id": message.id,
                    }
                )

                if saved:
                    collected += 1
                    if collected % 10 == 0:
                        print(f"   ✅ Collected {collected} posts from @{channel_username}")
                else:
                    skipped += 1

            except Exception:
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

    client = TelegramClient('bioguard_session', API_ID, API_HASH)
    await client.start(phone=PHONE)
    print("\n✅ Telegram client connected!")

    total_collected = 0
    for channel in CHANNELS:
        count = await collect_from_channel(client, channel, days_back)
        total_collected += count

    await client.disconnect()

    print(f"\n{'='*50}")
    print(f"✅ COLLECTION COMPLETE")
    print(f"   Total posts collected: {total_collected}")

    from database import social_posts
    real_count = social_posts.count_documents({"simulated": False})
    print(f"   Total real posts in MongoDB: {real_count}")
    print(f"{'='*50}")

    return total_collected


def collect_telegram_data(days_back=90):
    """Synchronous wrapper — call this from app.py or social_media_manager."""
    return asyncio.run(run_collector(days_back))


if __name__ == "__main__":
    collect_telegram_data(days_back=90)