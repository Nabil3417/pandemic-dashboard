import sys
import os
import random
from datetime import datetime, timedelta

# Add parent directory to path so we can import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import social_posts


# Realistic health-related posts based on actual social media patterns
SYMPTOM_POSTS = [
    "Feeling really sick today, high fever and body aches 😷",
    "Been coughing non-stop since yesterday, should I see a doctor?",
    "Headache won't go away, feeling exhausted",
    "My throat is so sore, can barely swallow",
    "Running a fever of 102°F, anyone else feeling sick?",
    "Caught the flu going around campus, staying home today",
    "Woke up with chills and muscle pain, not good",
    "Is there a flu outbreak? So many people are sick",
    "Apollo Hospital ER is packed, waited 2 hours",
    "Pharmacies running low on fever medicine in Bashundhara",
    "NSU campus clinic is super crowded today",
    "Half my class is absent because of illness",
    "Feeling weak and dizzy, lost my appetite",
    "My whole family has fever and cough now",
    "Anyone know a good doctor in Gulshan area? Feeling very sick",
]

NORMAL_POSTS = [
    "Beautiful weather in Dhaka today! ☀️",
    "Just finished my morning workout, feeling great!",
    "Coffee at the new café in Bashundhara 😊",
    "Finally weekend! Time to relax",
    "Studying for finals at NSU library",
    "Traffic is surprisingly light today",
    "Had an amazing dinner at Banani restaurant",
    "Movie night with friends 🎬",
    "Morning walk at Hatirjheel, so peaceful",
    "Got my flu shot today, stay healthy everyone!",
    "Enjoying the cool evening breeze",
    "Friday prayers at the mosque",
    "Shopping at Jamuna Future Park",
    "Playing cricket at Uttara stadium",
    "Happy to be healthy and safe today!",
]

LOCATIONS = [
    {"zone_id": 1, "name": "Bashundhara R/A", "lat": 23.8191, "lng": 90.4526},
    {"zone_id": 2, "name": "Banani", "lat": 23.7940, "lng": 90.4043},
    {"zone_id": 3, "name": "Uttara", "lat": 23.8759, "lng": 90.3795},
]

PLATFORMS = ["Twitter", "Reddit", "Facebook", "Instagram"]


def generate_social_media_data(days=30, posts_per_day=20):
    """
    Generates realistic social media posts with outbreak pattern
    
    Args:
        days: Number of days to simulate (default 30)
        posts_per_day: Average posts per day (default 20)
    """
    
    print(f"🚀 Generating {days} days of social media data...")
    
    start_date = datetime.now() - timedelta(days=days)
    outbreak_start_day = 20  # Outbreak starts on day 20
    
    generated_posts = []
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        # Determine if this is during outbreak period
        is_outbreak = day >= outbreak_start_day
        
        # More symptom posts during outbreak
        if is_outbreak:
            symptom_ratio = 0.65  # 65% symptom posts during outbreak
        else:
            symptom_ratio = 0.15  # 15% symptom posts normally
        
        # Generate posts for this day
        num_posts = random.randint(posts_per_day - 5, posts_per_day + 5)
        
        for _ in range(num_posts):
            # Decide if this post mentions symptoms
            is_symptom_post = random.random() < symptom_ratio
            
            # Select post text
            if is_symptom_post:
                text = random.choice(SYMPTOM_POSTS)
            else:
                text = random.choice(NORMAL_POSTS)
            
            # Select location (outbreak concentrated in Zone 1 - Bashundhara)
            if is_outbreak and is_symptom_post:
                # 70% of outbreak posts from Zone 1
                if random.random() < 0.7:
                    location = LOCATIONS[0]  # Bashundhara
                else:
                    location = random.choice(LOCATIONS)
            else:
                location = random.choice(LOCATIONS)
            
            # Random time during the day
            hour = random.randint(6, 23)
            minute = random.randint(0, 59)
            timestamp = current_date.replace(hour=hour, minute=minute)
            
            # Create post document
            post = {
                "text": text,
                "platform": random.choice(PLATFORMS),
                "timestamp": timestamp,
                "zone_id": location["zone_id"],
                "location_name": location["name"],
                "latitude": location["lat"] + random.uniform(-0.01, 0.01),
                "longitude": location["lng"] + random.uniform(-0.01, 0.01),
                "processed": False,
                "bert_score": None,
                "is_symptom": is_symptom_post,
                "simulated": True
            }
            
            generated_posts.append(post)
    
    # Insert into MongoDB
    if generated_posts:
        social_posts.insert_many(generated_posts)
        print(f"✅ Generated and inserted {len(generated_posts)} social media posts!")
        
        # Statistics
        symptom_count = sum(1 for p in generated_posts if p['is_symptom'])
        normal_count = len(generated_posts) - symptom_count
        
        print(f"\n📊 Statistics:")
        print(f"   Total Posts: {len(generated_posts)}")
        print(f"   Symptom-related: {symptom_count} ({symptom_count/len(generated_posts)*100:.1f}%)")
        print(f"   Normal posts: {normal_count} ({normal_count/len(generated_posts)*100:.1f}%)")
        print(f"   Date range: {start_date.date()} to {current_date.date()}")
        print(f"   Outbreak simulation starts: Day {outbreak_start_day}")
        
        # Zone distribution
        zone_counts = {}
        for post in generated_posts:
            zone = post['location_name']
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
        
        print(f"\n📍 Location Distribution:")
        for zone, count in zone_counts.items():
            print(f"   {zone}: {count} posts")
    
    return len(generated_posts)


if __name__ == "__main__":
    # Clear existing simulated data
    deleted = social_posts.delete_many({"simulated": True})
    print(f"🗑️  Cleared {deleted.deleted_count} old simulated posts\n")
    
    # Generate new data
    generate_social_media_data(days=30, posts_per_day=20)
    
    print("\n✅ Social media data generation complete!")
    print("💡 Run 'python backend/database.py' to verify data was stored")