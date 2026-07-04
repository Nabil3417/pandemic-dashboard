"""Test mobility API responses without Flask server."""
from data_collectors.mobility_repository import MobilityRepository

repo = MobilityRepository()

print("=" * 60)
print("  Testing API Response Formats")
print("=" * 60)

# Test 1: All zones
data = repo.api_mobility_detail()
print(f"\n  1. All zones: {len(data['zones'])} zones, risk={data['risk_summary']}")
print(f"     Keys: {list(data.keys())}")

# Test 2: Single zone
data = repo.api_mobility_detail(zone_id=15)
print(f"\n  2. Zone 15: {data['zone']['zone_name']}, score={data['zone']['wdzmi_score']}")
print(f"     History: {len(data['history'])} records")
print(f"     Neighbors: {len(data['neighbors'])} zones")

# Test 3: Risk status
data = repo.api_risk_status()
print(f"\n  3. Risk status: avg={data['avg_score']}, top={data['top_zones'][0]['zone_name']}")
print(f"     Keys: {list(data.keys())}")

# Test 4: Signal breakdown
detail = repo.get_signal_detail(15)
print(f"\n  4. Signal breakdown for Zone 15:")
for sig, info in detail.items():
    print(f"     {sig}: score={info['score']}, weight={info['weight']}, contribution={info['contribution']}")

# Test 5: Top/bottom
top = repo.get_top_zones(3)
bottom = repo.get_bottom_zones(3)
print(f"\n  5. Top 3: {[z['zone_name'] for z in top]}")
print(f"     Bottom 3: {[z['zone_name'] for z in bottom]}")

repo.close()
print("\n  All API response formats verified!")
print("=" * 60)