"""
BioGuard AI — Model Evaluation Script
======================================
Evaluates the multi-modal fusion model against real historical outbreak data.

What this script does:
  1. Loads outbreak_ground_truth.csv (156 labeled weeks, 2020-2022)
  2. Loads real historical Google Trends + mobility data for the same period
  3. Replays the fusion model week-by-week on historical data
  4. Computes Precision, Recall, F1, ROC-AUC, Confusion Matrix
  5. Runs per-modality analysis (each signal alone vs combined)
  6. Saves all results to data/evaluation_results.json
  7. Prints a clean results table to console

Run once after all data collectors have been run:
  cd backend
  python evaluate.py
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# ── path setup so we can import from backend root ─────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import trends_data, iedcr_reports

# ── sklearn metrics ───────────────────────────────────────────────────────────
try:
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        roc_auc_score, confusion_matrix, classification_report
    )
except ImportError:
    print("❌ scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)

# ── constants ─────────────────────────────────────────────────────────────────
DATA_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GROUND_TRUTH    = os.path.join(DATA_DIR, "outbreak_ground_truth.csv")
MOBILITY_CSV    = os.path.join(DATA_DIR, "dhaka_zone_mobility_2020_2022.csv")
TRENDS_CSV      = os.path.join(DATA_DIR, "dhaka_zone_symptom_trends.csv")
OUTPUT_JSON     = os.path.join(DATA_DIR, "evaluation_results.json")

# Fusion weights — must match app.py
NLP_WEIGHT        = 0.30
WASTEWATER_WEIGHT = 0.50
MOBILITY_WEIGHT   = 0.20

# Outbreak threshold — fused score above this = predicted outbreak
OUTBREAK_THRESHOLD = 22.0

# Zone to use for single-zone evaluation (zone 11 = Motijheel/central Dhaka)
EVAL_ZONE = 11


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load ground truth
# ══════════════════════════════════════════════════════════════════════════════

def load_ground_truth():
    print("\n📋 Loading ground truth labels...")
    df = pd.read_csv(GROUND_TRUTH)
    df['date_start'] = pd.to_datetime(df['date_start'])
    df['date_end']   = pd.to_datetime(df['date_end'])
    print(f"   Total weeks    : {len(df)}")
    print(f"   Outbreak weeks : {df['outbreak_label'].sum()}")
    print(f"   Normal weeks   : {(df['outbreak_label'] == 0).sum()}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Load historical signal data
# ══════════════════════════════════════════════════════════════════════════════

def load_trends_series(zone_id=EVAL_ZONE):
    """Load weekly symptom-search scores for a zone from MongoDB or CSV fallback."""
    print(f"\n📈 Loading Google Trends series (zone {zone_id})...")

    # Try MongoDB first
    docs = list(trends_data.find(
        {"zone_id": zone_id},
        sort=[("date", 1)]
    ))
    if docs:
        df = pd.DataFrame([{"date": d["date"], "symptom_score": d["symptom_score"]} for d in docs])
        df['date'] = pd.to_datetime(df['date'])
        print(f"   Loaded {len(df)} records from MongoDB")
        return df

    # Fallback to CSV
    if os.path.exists(TRENDS_CSV):
        df = pd.read_csv(TRENDS_CSV)
        df['date'] = pd.to_datetime(df['date'])
        zone_df = df[df['zone_id'] == zone_id].sort_values('date').reset_index(drop=True)
        print(f"   Loaded {len(zone_df)} records from CSV")
        return zone_df[['date', 'symptom_score']]

    print("   ⚠️  No trends data found — using zeros")
    return pd.DataFrame(columns=['date', 'symptom_score'])


def load_mobility_series(zone_id=EVAL_ZONE):
    """Load weekly mobility risk scores for a zone."""
    print(f"\n🚶 Loading mobility series (zone {zone_id})...")

    if not os.path.exists(MOBILITY_CSV):
        print("   ⚠️  Mobility CSV not found — using zeros")
        return pd.DataFrame(columns=['date', 'mobility_score'])

    df = pd.read_csv(MOBILITY_CSV)
    df.columns = df.columns.str.strip().str.lower()

    # Detect date column
    date_col = next((c for c in df.columns if 'date' in c), None)
    if not date_col:
        print("   ⚠️  No date column found in mobility CSV")
        return pd.DataFrame(columns=['date', 'mobility_score'])

    df[date_col] = pd.to_datetime(df[date_col])

    # Detect zone column and score column
    zone_col  = next((c for c in df.columns if 'zone' in c), None)
    score_col = next((c for c in df.columns if any(x in c for x in ['score', 'risk', 'mobility', 'anomaly'])), None)

    if zone_col and score_col:
        zone_df = df[df[zone_col] == zone_id].copy()
        zone_df = zone_df.rename(columns={date_col: 'date', score_col: 'mobility_score'})
        zone_df = zone_df[['date', 'mobility_score']].sort_values('date').reset_index(drop=True)
        print(f"   Loaded {len(zone_df)} zone-specific records")
        return zone_df
    elif score_col:
        # No zone column — use all records as aggregate
        df = df.rename(columns={date_col: 'date', score_col: 'mobility_score'})
        df = df[['date', 'mobility_score']].sort_values('date').reset_index(drop=True)
        print(f"   Loaded {len(df)} aggregate records (no zone column)")
        return df
    else:
        print(f"   ⚠️  Could not identify score column. Columns: {list(df.columns)}")
        return pd.DataFrame(columns=['date', 'mobility_score'])


def load_iedcr_series():
    """Load monthly IEDCR normalized scores and expand to weekly."""
    print("\n🏥 Loading IEDCR/DGHS series...")
    docs = list(iedcr_reports.find(
        {"disease": "dengue", "division": "Dhaka"},
        sort=[("year", 1), ("month", 1)]
    ))
    if not docs:
        print("   ⚠️  No IEDCR data found — using zeros")
        return pd.DataFrame(columns=['date', 'iedcr_score'])

    records = []
    for d in docs:
        # Create a date from year+month
        try:
            date = datetime(int(d['year']), int(d['month']), 1)
            records.append({"date": date, "iedcr_score": d.get("normalized_score", 0.0)})
        except Exception:
            continue

    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    print(f"   Loaded {len(df)} monthly IEDCR records")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Align signals to ground truth weeks
# ══════════════════════════════════════════════════════════════════════════════

def get_signal_for_week(signal_df, date_start, date_end, score_col):
    """Get the mean signal value for a given week window."""
    if signal_df.empty:
        return 0.0
    mask = (signal_df['date'] >= date_start) & (signal_df['date'] <= date_end)
    subset = signal_df[mask]
    if subset.empty:
        # Use nearest available value
        idx = (signal_df['date'] - date_start).abs().idxmin()
        return float(signal_df.iloc[idx][score_col])
    return float(subset[score_col].mean())


def build_weekly_signals(gt_df, trends_df, mobility_df, iedcr_df):
    """
    For each ground truth week, extract the corresponding signal values.
    Returns a DataFrame with columns:
      week, date_start, outbreak_label,
      trends_score, mobility_score, iedcr_score, fused_score
    """
    print("\n⚙️  Aligning signals to ground truth weeks...")
    rows = []

    for _, row in gt_df.iterrows():
        date_start = row['date_start']
        date_end   = row['date_end']

        # Filter to 2020-2022 period only
        if date_start.year < 2020 or date_start.year > 2022:
            continue

        # Get each signal
        trends_score   = get_signal_for_week(trends_df, date_start, date_end, 'symptom_score')
        mobility_score = get_signal_for_week(mobility_df, date_start, date_end, 'mobility_score')
        iedcr_score    = get_signal_for_week(iedcr_df, date_start, date_end, 'iedcr_score')

        # All scores already 0-100 — just clamp
        trends_score   = min(max(float(trends_score), 0), 100)
        mobility_score = min(max(float(mobility_score), 0), 100)
        iedcr_score    = min(max(float(iedcr_score), 0), 100)  # already normalized in MongoDB

        # Wastewater proxy = blend of trends (60%) + iedcr (40%)
        wastewater_proxy = (trends_score * 0.6) + (iedcr_score * 0.4)

        # NLP proxy — use trends score as NLP proxy for historical evaluation
        # (we don't have historical BERT scores, so symptom search is the best proxy)
        nlp_proxy = trends_score

        # Fused score — same weights as app.py
        fused = (
            nlp_proxy        * NLP_WEIGHT +
            wastewater_proxy * WASTEWATER_WEIGHT +
            mobility_score   * MOBILITY_WEIGHT
        )

        rows.append({
            "week":            f"{row['year']}-W{row['week_number']:02d}",
            "date_start":      date_start,
            "year":            row['year'],
            "outbreak_label":  int(row['outbreak_label']),
            "trends_score":    round(trends_score, 2),
            "mobility_score":  round(mobility_score, 2),
            "iedcr_score":     round(iedcr_score, 2),
            "wastewater_proxy":round(wastewater_proxy, 2),
            "nlp_proxy":       round(nlp_proxy, 2),
            "fused_score":     round(fused, 2),
        })

    df = pd.DataFrame(rows)
    print(f"   Built {len(df)} aligned weekly records")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Compute metrics
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(y_true, y_pred, y_scores, label="Combined Model"):
    """Compute and return all evaluation metrics."""
    prec  = precision_score(y_true, y_pred, zero_division=0)
    rec   = recall_score(y_true, y_pred, zero_division=0)
    f1    = f1_score(y_true, y_pred, zero_division=0)
    cm    = confusion_matrix(y_true, y_pred)

    try:
        auc = roc_auc_score(y_true, y_scores)
    except Exception:
        auc = 0.0

    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

    return {
        "label":      label,
        "precision":  round(float(prec), 4),
        "recall":     round(float(rec), 4),
        "f1_score":   round(float(f1), 4),
        "roc_auc":    round(float(auc), 4),
        "tp":         int(tp),
        "fp":         int(fp),
        "tn":         int(tn),
        "fn":         int(fn),
        "threshold":  OUTBREAK_THRESHOLD,
        "total_weeks": len(y_true),
        "outbreak_weeks": int(sum(y_true)),
    }


def predict_from_score(scores, threshold=OUTBREAK_THRESHOLD):
    return [1 if s >= threshold else 0 for s in scores]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Per-modality analysis
# ══════════════════════════════════════════════════════════════════════════════

def run_modality_analysis(aligned_df):
    """Run each modality alone and compute F1 to see individual contribution."""
    print("\n🔬 Running per-modality analysis...")
    results = {}
    y_true  = aligned_df['outbreak_label'].tolist()

    modalities = {
        "NLP only (symptom search proxy)": "nlp_proxy",
        "Mobility only":                   "mobility_score",
        "Wastewater proxy only":           "wastewater_proxy",
    }

    for label, col in modalities.items():
        scores  = aligned_df[col].tolist()
        y_pred  = predict_from_score(scores)
        metrics = compute_metrics(y_true, y_pred, scores, label=label)
        results[col] = metrics
        print(f"   {label:<35} F1={metrics['f1_score']:.3f}  AUC={metrics['roc_auc']:.3f}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Early warning analysis
# ══════════════════════════════════════════════════════════════════════════════

def compute_early_warning(aligned_df):
    """
    For each known outbreak, check how many weeks BEFORE the outbreak start
    the model's fused score crossed the threshold.
    Returns average early warning lead time in weeks.
    """
    print("\n⏱️  Computing early warning lead time...")

    gt_df   = aligned_df.copy()
    results = []

    # Find outbreak start weeks (transition from 0 to 1)
    gt_df = gt_df.sort_values('date_start').reset_index(drop=True)
    for i in range(1, len(gt_df)):
        if gt_df.iloc[i]['outbreak_label'] == 1 and gt_df.iloc[i-1]['outbreak_label'] == 0:
            outbreak_start = gt_df.iloc[i]['date_start']

            # Look back up to 4 weeks before outbreak start
            for lookback in range(1, 5):
                j = i - lookback
                if j < 0:
                    break
                if gt_df.iloc[j]['fused_score'] >= OUTBREAK_THRESHOLD:
                    results.append(lookback)
                    print(f"   Outbreak {outbreak_start.date()} — model flagged {lookback} week(s) early")
                    break

    if results:
        avg_lead = round(np.mean(results), 1)
        print(f"   Average early warning lead time: {avg_lead} weeks")
    else:
        avg_lead = 0
        print("   ⚠️  No early warnings detected at current threshold")

    return {
        "avg_lead_weeks":       avg_lead,
        "outbreaks_detected_early": len(results),
        "lead_times":           results,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run_evaluation():
    print("=" * 65)
    print("BioGuard AI — Model Evaluation")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    # ── Load all data ──────────────────────────────────────────────────────
    gt_df       = load_ground_truth()
    trends_df   = load_trends_series(zone_id=EVAL_ZONE)
    mobility_df = load_mobility_series(zone_id=EVAL_ZONE)
    iedcr_df    = load_iedcr_series()

    # ── Align signals to weeks ─────────────────────────────────────────────
    aligned_df = build_weekly_signals(gt_df, trends_df, mobility_df, iedcr_df)

    if aligned_df.empty:
        print("❌ No aligned data produced — check your CSV files and MongoDB collections")
        return

    y_true  = aligned_df['outbreak_label'].tolist()
    scores  = aligned_df['fused_score'].tolist()
    y_pred  = predict_from_score(scores)

    # ── Combined model metrics ─────────────────────────────────────────────
    print("\n📊 Computing combined model metrics...")
    combined = compute_metrics(y_true, y_pred, scores, label="Combined Model (NLP+Mobility+Wastewater)")

    print(f"\n{'='*65}")
    print("COMBINED MODEL RESULTS")
    print(f"{'='*65}")
    print(f"  Precision : {combined['precision']:.4f}  ({combined['precision']*100:.1f}%)")
    print(f"  Recall    : {combined['recall']:.4f}  ({combined['recall']*100:.1f}%)")
    print(f"  F1 Score  : {combined['f1_score']:.4f}  ({combined['f1_score']*100:.1f}%)")
    print(f"  ROC-AUC   : {combined['roc_auc']:.4f}  ({combined['roc_auc']*100:.1f}%)")
    print(f"\n  Confusion Matrix:")
    print(f"             Predicted")
    print(f"             Normal  Outbreak")
    print(f"  Actual Normal  : {combined['tn']:>4}    {combined['fp']:>4}")
    print(f"  Actual Outbreak: {combined['fn']:>4}    {combined['tp']:>4}")
    print(f"{'='*65}")

    # ── Per-modality analysis ──────────────────────────────────────────────
    modality_results = run_modality_analysis(aligned_df)

    # ── Early warning analysis ─────────────────────────────────────────────
    early_warning = compute_early_warning(aligned_df)

    # ── Build final output ─────────────────────────────────────────════════
    output = {
        "generated_at":     datetime.now().isoformat(),
        "eval_zone":        EVAL_ZONE,
        "total_weeks":      len(aligned_df),
        "outbreak_weeks":   int(sum(y_true)),
        "normal_weeks":     int(len(y_true) - sum(y_true)),
        "threshold":        OUTBREAK_THRESHOLD,
        "fusion_weights": {
            "nlp":        NLP_WEIGHT,
            "wastewater": WASTEWATER_WEIGHT,
            "mobility":   MOBILITY_WEIGHT,
        },
        "combined_model": combined,
        "per_modality": {
            "nlp_only": {
                **modality_results.get("nlp_proxy", {}),
                "weight_in_fusion": NLP_WEIGHT,
            },
            "mobility_only": {
                **modality_results.get("mobility_score", {}),
                "weight_in_fusion": MOBILITY_WEIGHT,
            },
            "wastewater_only": {
                **modality_results.get("wastewater_proxy", {}),
                "weight_in_fusion": WASTEWATER_WEIGHT,
            },
        },
        "early_warning":    early_warning,
        "model_comparison": {
            "note": "Fine-tuned BanglaBERT comparison will be added after fine_tune_bert.py is run",
            "base_model_f1":      combined['f1_score'],
            "finetuned_model_f1": None,
        },
        "data_sources": {
            "trends":   "Google Trends symptom-search (MongoDB + CSV)",
            "mobility": "dhaka_zone_mobility_2020_2022.csv",
            "iedcr":    "DGHS/IEDCR dengue case data (MongoDB)",
        },
    }

    # ── Save JSON ──────────────────────────────────────────────────────────
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✅ Results saved to: {OUTPUT_JSON}")
    print(f"\n📋 MODALITY COMPARISON:")
    print(f"   {'Signal':<35} {'F1':>6}  {'AUC':>6}")
    print(f"   {'-'*50}")
    for key, m in modality_results.items():
        print(f"   {m['label']:<35} {m['f1_score']:>6.3f}  {m['roc_auc']:>6.3f}")
    print(f"   {'Combined (all three)':<35} {combined['f1_score']:>6.3f}  {combined['roc_auc']:>6.3f}")
    print(f"\n⏱️  Early warning: system flags outbreaks {early_warning['avg_lead_weeks']} weeks early on average")
    print(f"\n{'='*65}")


if __name__ == "__main__":
    run_evaluation()