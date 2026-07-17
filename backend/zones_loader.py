"""
zones_loader.py — Single source of truth for BioGuard AI zone metadata.

All zone definitions (id, name, coordinates, density, weights, keywords)
are loaded from backend/data/zones.json. No other file should hardcode
zone metadata.

Usage:
    from zones_loader import load_zones_dict, get_zone_by_id, ZONES_LIST

    # Dict keyed by int zone_id (for engine_mobility, engine_wastewater, etc.)
    zones = load_zones_dict()
    print(zones[1]['name'])  # "Uttara"

    # List format (for app.py)
    for z in ZONES_LIST:
        print(z['id'], z['name'])

    # Keywords dict (for base_collector.py)
    from zones_loader import ZONE_KEYWORDS, ZONE_COORDS
"""

import json
import os

_ZONES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'zones.json')
_cache = None


def _load_raw():
    """Load and cache the full zones.json file."""
    global _cache
    if _cache is None:
        with open(_ZONES_PATH, 'r', encoding='utf-8') as f:
            _cache = json.load(f)
    return _cache


def load_zones_dict():
    """
    Return zones as a dict keyed by int zone_id.
    Each value is the full zone dict from zones.json.

    Example: zones[1]['name'] -> "Uttara"
    """
    raw = _load_raw()
    return {int(k): v for k, v in raw['zones'].items()}


def get_zone_by_id(zone_id):
    """Return a single zone dict, or None if not found."""
    return load_zones_dict().get(int(zone_id))


def get_all_zone_ids():
    """Return sorted list of all zone IDs."""
    return sorted(load_zones_dict().keys())


# ─────────────────────────────────────────────
# Pre-built convenience views (lazily built once)
# ─────────────────────────────────────────────

def _build_zones_list():
    """Build app.py-compatible list of zone dicts."""
    zones = load_zones_dict()
    result = []
    for zid in sorted(zones.keys()):
        z = zones[zid]
        result.append({
            "id":           z["id"],
            "city":         z["name"],
            "area":         z["area"],
            "corporation":  z["corporation"],
            "center":       z["center"],
            "signal":       z["signal"],
            "mobility":     z["default_mobility"],
        })
    return result


def _build_zone_profiles():
    """Build engine_mobility.py-compatible ZONE_PROFILES dict."""
    zones = load_zones_dict()
    result = {}
    for zid, z in zones.items():
        result[zid] = {
            "name":        z["name"],
            "center":      tuple(z["center"]),
            "density":     z["density_class"],
            "min_cluster": z["min_cluster"],
        }
    return result


def _build_ww_profiles():
    """Build engine_wastewater.py-compatible ZONE_PROFILES dict."""
    zones = load_zones_dict()
    result = {}
    for zid, z in zones.items():
        result[zid] = {
            "name":       z["name"],
            "baseline":   z["ww_baseline"],
            "volatility": z["ww_volatility"],
        }
    return result


def _build_zone_weights():
    """Build generate_zone_csv.py-compatible ZONE_WEIGHTS dict."""
    zones = load_zones_dict()
    return {zid: z["zone_weight"] for zid, z in zones.items()}


def _build_keywords_dict():
    """Build base_collector.py-compatible ZONE_KEYWORDS dict."""
    zones = load_zones_dict()
    return {zid: z["keywords"] for zid, z in zones.items()}


def _build_coords_dict():
    """Build base_collector.py-compatible ZONE_COORDS dict."""
    zones = load_zones_dict()
    result = {}
    for zid, z in zones.items():
        result[zid] = {
            "lat":  z["center"][0],
            "lng":  z["center"][1],
            "name": z["name"],
        }
    return result


def _build_density_spread():
    """Build engine_mobility.py-compatible DENSITY_SPREAD dict."""
    return {
        "low":       0.015,
        "medium":    0.010,
        "high":      0.007,
        "very_high": 0.005,
    }


# ─────────────────────────────────────────────
# Lazy module-level attributes via __getattr__
# ─────────────────────────────────────────────
#
# Python 3.7+ module __getattr__ is the ONLY pattern that correctly
# intercepts `from zones_loader import ZONE_PROFILES`.  Class-based
# descriptors (_LazyAttr) do NOT work because `from X import Y`
# fetches the raw descriptor object — __get__ is never called.

_LAZY_REGISTRY = {
    "ZONES_LIST":      _build_zones_list,
    "ZONE_PROFILES":   _build_zone_profiles,
    "DENSITY_SPREAD":  _build_density_spread,
    "WW_ZONE_PROFILES": _build_ww_profiles,
    "ZONE_WEIGHTS":    _build_zone_weights,
    "ZONE_KEYWORDS":   _build_keywords_dict,
    "ZONE_COORDS":     _build_coords_dict,
}

# Once a value is built, cache it directly as a module attribute
# so subsequent imports hit the cached dict/list, not __getattr__.
def __getattr__(name):
    if name in _LAZY_REGISTRY:
        value = _LAZY_REGISTRY[name]()
        globals()[name] = value          # cache for future lookups
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")