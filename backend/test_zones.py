import json

z = json.load(open('data/zones.json', encoding='utf-8'))
c = json.load(open('data/corridors.json', encoding='utf-8'))

print(f"Zones: {len(z['zones'])}")
print(f"Corridors: {len(c['corridors'])}")
print(f"Update interval: {c['metadata']['update_interval_minutes']} min")
print()

total_weight = 0
zone_coverage = set()
for cor in c['corridors']:
    total_weight += cor['weight']
    zone_coverage.add(cor['origin_zone'])
    zone_coverage.add(cor['destination_zone'])

print(f"Total corridor weight: {total_weight:.2f}")
print(f"Zones covered by corridors: {len(zone_coverage)}/15")
print(f"Missing zones: {set(range(1,16)) - zone_coverage}")
print()

print("--- Top 5 corridors by weight ---")
for cor in sorted(c['corridors'], key=lambda x: x['weight'], reverse=True)[:5]:
    oz = z['zones'][str(cor['origin_zone'])]['name']
    dz = z['zones'][str(cor['destination_zone'])]['name']
    print(f"  {cor['id']} ({cor['weight']:.2f}) {oz} -> {dz}")