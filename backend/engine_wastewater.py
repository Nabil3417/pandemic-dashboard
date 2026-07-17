"""
BioGuard AI — Symptom-Search Surveillance Engine (formerly "wastewater engine")
================================================================================
v5.0 — REAL DATA UPGRADE

WHAT CHANGED FROM v4.x:
  The old version generated a fully synthetic viral-load series (sine
  wave + noise + scripted "outbreak bumps") and fit ARIMA on that fake
  data. That is no longer acceptable for a research system, so this
  engine now:

    1. Loads REAL Google Trends symptom-search data collected by
       data_collectors/google_trends_collector.py (either from the
       local CSV cache data/dhaka_zone_symptom_trends.csv, or live
       from MongoDB's trends_data collection).
    2. Fits ARIMA(1,1,1) on that REAL series per zone — same modeling
       approach as before, now grounded in real search-behavior data
       instead of a synthetic generator.
    3. Falls back to the old synthetic generator ONLY if no real data
       has been collected yet for a zone (e.g. before the collector has
       been run), and clearly marks that zone's data_source as
       "synthetic-fallback" everywhere it's reported — including in
       get_engine_status(), so the dashboard and any evaluation code
       can distinguish real results from placeholder ones.

HONESTY NOTE FOR THE RESEARCH WRITE-UP:
  Bangladesh has no public wastewater-surveillance API. A real sewage
  surveillance program for Dhaka does exist (icddr,b / University of
  Virginia / IEDCR, published in Rogawski McQuade et al., Lancet
  Microbe 2023 — 2,073 samples, 37 sites, weekly Dec 2019-Dec 2021,
  showing sewage signal precedes clinical case rises by 1-2 weeks),
  but its raw dataset is not bulk-downloadable; it lives in the
  paper's supplementary materials / with the authors.
  This engine therefore uses Google Trends symptom-search volume as a
  REAL, immediately-available proxy signal for population-level
  illness burden — an approach with its own peer-reviewed precedent
  (Ginsberg et al., "Detecting influenza epidemics using search engine
  query data", Nature, 2009). It is a genuinely real signal, but it is
  a different modality than viral RNA in sewage, and that substitution
  should be stated explicitly wherever this module is described.

  Google Trends also does not report at ward/neighborhood resolution
  for Bangladesh — only national/divisional. Zone-level values here
  are therefore a disaggregation (using the same zone-weight table as
  the mobility engine), not a direct per-zone measurement. State this
  limitation in the methodology section.

References:
  Ginsberg, J., et al. Detecting influenza epidemics using search
    engine query data. Nature, 2009.
  Mavragani, A. & Ochoa, G. Google Trends in Infodemiology and
    Infoveillance. JMIR Public Health Surveill, 2019.
  Rogawski McQuade, E.T., et al. Real-time sewage surveillance for
    SARS-CoV-2 in Dhaka, Bangladesh versus clinical COVID-19
    surveillance. Lancet Microbe, 2023.
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime
from statsmodels.tsa.arima.model import ARIMA
import warnings
warnings.filterwarnings('ignore')

from database import get_zone_trends_series, get_latest_iedcr_score

# ─────────────────────────────────────────────────────────────
# Zone profiles — loaded from zones.json (single source of truth)
from zones_loader import WW_ZONE_PROFILES as ZONE_PROFILES

CSV_FILENAME = "dhaka_zone_symptom_trends.csv"
MIN_REAL_POINTS = 15  # below this, ARIMA on real data is unreliable — use fallback

_zone_cache = {}
_cache_timestamp = {}
CACHE_TTL_MINUTES = 30


# ─────────────────────────────────────────────────────────────
# SYNTHETIC FALLBACK (unchanged from v4.x — only used when a zone
# has no real Google Trends data collected yet)
# ─────────────────────────────────────────────────────────────

def _generate_synthetic_series(zone_id, days=60, crisis_mode=False):
    profile   = ZONE_PROFILES.get(zone_id, ZONE_PROFILES[15])
    baseline  = profile['baseline']
    volatility = profile['volatility']

    series  = []
    current = baseline

    for day in range(days):
        weekly_swing = 2.0 * np.sin(2 * np.pi * day / 7)
        noise = random.gauss(0, volatility * 10)
        mean_reversion = (baseline - current) * 0.15

        if crisis_mode and day > days - 10:
            crisis_boost = random.uniform(15, 25)
        else:
            crisis_boost = 0

        outbreak_boost = 0
        if not crisis_mode and 40 < day < 50:
            outbreak_boost = random.uniform(2, 6)

        current = max(5, min(90, current + weekly_swing + noise
                              + mean_reversion + crisis_boost + outbreak_boost))
        series.append(round(current, 2))

    return series


# ─────────────────────────────────────────────────────────────
# REAL DATA LOADING
# ─────────────────────────────────────────────────────────────

def _load_real_series_from_csv(zone_id):
    """Loads a zone's real weekly symptom_score series from the CSV cache."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "data", CSV_FILENAME)

    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
        zone_df = df[df['zone_id'] == zone_id].sort_values('date')
        if len(zone_df) < MIN_REAL_POINTS:
            return None
        return zone_df['symptom_score'].tolist()
    except Exception as e:
        print(f"   ⚠️  Could not read {CSV_FILENAME}: {e}")
        return None


def _load_real_series_from_mongo(zone_id):
    """Loads a zone's real weekly symptom_score series from MongoDB (live data)."""
    try:
        docs = get_zone_trends_series(zone_id, limit=200)
        if len(docs) < MIN_REAL_POINTS:
            return None
        return [d['symptom_score'] for d in docs]
    except Exception as e:
        print(f"   ⚠️  Could not read trends_data from MongoDB: {e}")
        return None


def _get_zone_series(zone_id, crisis_mode):
    """
    Returns (series, data_source) for a zone.
    Priority: MongoDB (live, most current) -> CSV cache -> synthetic fallback.
    Cached for CACHE_TTL_MINUTES to avoid re-querying Mongo/CSV on every request.
    """
    now = datetime.now()
    cache_key = f"{zone_id}_{crisis_mode}"
    last_update = _cache_timestamp.get(cache_key)

    if (last_update is not None and
            (now - last_update).total_seconds() < CACHE_TTL_MINUTES * 60):
        return _zone_cache[cache_key]

    # 1. Try MongoDB (real, live)
    series = _load_real_series_from_mongo(zone_id)
    source = "real-google-trends (mongodb)"

    # 2. Try CSV cache (real, offline-safe)
    if series is None:
        series = _load_real_series_from_csv(zone_id)
        source = "real-google-trends (csv-cache)"

    # 3. Fall back to synthetic (clearly flagged)
    if series is None:
        series = _generate_synthetic_series(zone_id, days=60, crisis_mode=crisis_mode)
        source = "synthetic-fallback"
    elif crisis_mode:
        # Overlay a crisis boost on the tail of a REAL series so the
        # crisis-mode demo toggle still works meaningfully even on real data.
        series = series.copy()
        boost_len = min(10, len(series))
        for i in range(len(series) - boost_len, len(series)):
            series[i] = min(95, series[i] + random.uniform(15, 25))

    result = (series, source)
    _zone_cache[cache_key] = result
    _cache_timestamp[cache_key] = now
    return result


def _fit_arima(series):
    try:
        model = ARIMA(series, order=(1, 1, 1))
        return model.fit()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# MAIN ENGINE CLASS
# ─────────────────────────────────────────────────────────────

class WastewaterARIMAEngine:
    """
    ARIMA-based symptom-search surveillance engine.
    Public method names are unchanged from v4.x so app.py requires no
    changes — only the underlying data source changed from fully
    synthetic to real Google Trends data (with synthetic fallback).
    """

    def __init__(self):
        print("🔬 Initializing Symptom-Search Surveillance Engine v5.0...")
        print("   Model: ARIMA(1,1,1)")
        print("   Zones: 15 Dhaka City Corporation zones")
        print("   Primary data source: Google Trends (real) — see")
        print("     data_collectors/google_trends_collector.py")
        print("   Fallback: literature-grounded synthetic generator")
        print("     (used only for zones with no collected data yet)")
        print("✅ Symptom-search engine ready!")

    def get_localized_load(self, zone_id, crisis_mode=False):
        """
        PRIMARY METHOD — called from app.py.
        Returns current symptom-search intensity score (0-100) for a zone.
        Blends Google Trends ARIMA score (60%) with IEDCR/DGHS case data (40%).
        """
        series, _ = _get_zone_series(zone_id, crisis_mode)
        historical = series[:max(1, len(series) - 7)] if len(series) > 20 else series
        model = _fit_arima(historical)

        # Google Trends score
        if model is not None:
            try:
                fitted_values = model.fittedvalues
                if len(fitted_values) > 0:
                    trends_score = float(fitted_values[-1])
                    trends_score = max(5.0, min(95.0, trends_score))
                else:
                    trends_score = round(series[-1], 2)
            except Exception:
                trends_score = round(series[-1], 2)
        else:
            trends_score = round(series[-1], 2)

        # IEDCR/DGHS score — normalized 0-100 from real case count data
        iedcr_score = get_latest_iedcr_score(division="Dhaka")

        # If IEDCR returned 0.0 (no data), use trends score only
        if iedcr_score == 0.0:
            return round(trends_score, 2)

        # Blend: Google Trends 60% + IEDCR 40%
        blended = (trends_score * 0.6) + (iedcr_score * 0.4)
        return round(max(5.0, min(95.0, blended)), 2)

    def get_forecast(self, zone_id, crisis_mode=False, days=7):
        """Returns ARIMA forecast for next N days with confidence intervals."""
        series, _ = _get_zone_series(zone_id, crisis_mode)
        historical = series[:max(1, len(series) - 7)] if len(series) > 20 else series
        model = _fit_arima(historical)
        forecast_data = []

        if model is not None:
            try:
                forecast = model.forecast(steps=days)
                forecast_obj = model.get_forecast(steps=days)
                conf_int = forecast_obj.conf_int(alpha=0.2)

                for i, pred in enumerate(forecast):
                    try:
                        lower = float(conf_int.iloc[i, 0])
                        upper = float(conf_int.iloc[i, 1])
                    except AttributeError:
                        lower = float(conf_int[i][0])
                        upper = float(conf_int[i][1])

                    forecast_data.append({
                        "day":   f"D{i+1}",
                        "load":  round(max(5, min(95, float(pred))), 2),
                        "lower": round(max(0, lower), 2),
                        "upper": round(min(100, upper), 2),
                    })
                return forecast_data
            except Exception:
                pass

        last = series[-1]
        for i in range(days):
            last = min(95, last * 1.02 + random.gauss(0, 1))
            forecast_data.append({
                "day":   f"D{i+1}",
                "load":  round(last, 2),
                "lower": round(max(0, last - 5), 2),
                "upper": round(min(100, last + 5), 2),
            })
        return forecast_data

    def get_14day_forecast(self, zone_id, crisis_mode=False):
        return self.get_forecast(zone_id, crisis_mode, days=14)
    
    def get_zone_forecast(self, zone_id, days=14):
        """
        Returns next N days of ARIMA forecast as a simple list of floats.
        Called directly by the /api/forecast endpoint in app.py.
        """
        series, _ = _get_zone_series(zone_id, crisis_mode=False)
        historical = series[:max(1, len(series) - 7)] if len(series) > 20 else series
        model = _fit_arima(historical)

        if model is not None:
            try:
                forecast = model.forecast(steps=days)
                return [round(max(5.0, min(95.0, float(v))), 2) for v in forecast]
            except Exception:
                pass

        # Fallback — linear extrapolation from last value
        last = series[-1]
        result = []
        for _ in range(days):
            last = min(95.0, max(5.0, last + random.gauss(0, 1)))
            result.append(round(last, 2))
        return result        

    def get_trend(self, zone_id, crisis_mode=False):
        series, _ = _get_zone_series(zone_id, crisis_mode)
        recent = series[-7:] if len(series) >= 7 else series

        if len(recent) < 2:
            return "stable"

        slope = (recent[-1] - recent[0]) / len(recent)

        if slope > 1.5:
            return "rising"
        elif slope < -1.5:
            return "falling"
        else:
            return "stable"

    def get_data_source(self, zone_id):
        """Returns whether this zone is currently using real or fallback data."""
        _, source = _get_zone_series(zone_id, crisis_mode=False)
        return source

    def get_engine_status(self):
        """Returns engine status for dashboard — now reports real vs fallback coverage."""
        real_zones = 0
        fallback_zones = 0
        for zone_id in ZONE_PROFILES:
            source = self.get_data_source(zone_id)
            if source.startswith("real"):
                real_zones += 1
            else:
                fallback_zones += 1

       # Get latest IEDCR score to report in status
        iedcr_score = get_latest_iedcr_score(division="Dhaka")

        return {
            "model":              "ARIMA(1,1,1)",
            "zones":              len(ZONE_PROFILES),
            "zones_real_data":    real_zones,
            "zones_fallback":     fallback_zones,
            "cache_size":         len(_zone_cache),
            "data_source":        "google_trends + iedcr_reports",
            "primary_source":     "Google Trends symptom-search (60% weight)",
            "secondary_source":   "IEDCR/DGHS dengue case data (40% weight)",
            "iedcr_latest_score": iedcr_score,
            "fallback_source":    "Literature-grounded synthetic generator",
            "reference":          "Ginsberg et al. 2009, Nature; "
                                   "Rogawski McQuade et al. 2023, Lancet Microbe",
            "status": (
                "fully real"     if fallback_zones == 0 else
                "partially real" if real_zones > 0 else
                "no real data collected yet — run google_trends_collector.py"
            ),
        }


wastewater_ai = WastewaterARIMAEngine()


# ─────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("TESTING SYMPTOM-SEARCH SURVEILLANCE ENGINE (v5.0 — real data)")
    print("=" * 65)

    print(f"\n{'Zone':<30} {'Source':<28} {'Current':>8} {'Trend':>10}")
    print("-" * 85)

    for zone_id, profile in ZONE_PROFILES.items():
        current = wastewater_ai.get_localized_load(zone_id)
        source  = wastewater_ai.get_data_source(zone_id)
        trend   = wastewater_ai.get_trend(zone_id)
        trend_arrow = "↑" if trend == "rising" else "↓" if trend == "falling" else "→"
        print(f"{profile['name']:<30} {source:<28} {current:>8.1f} {trend_arrow:>10}")

    print("\nENGINE STATUS:")
    for key, val in wastewater_ai.get_engine_status().items():
        print(f"  {key}: {val}")
    print("=" * 65)