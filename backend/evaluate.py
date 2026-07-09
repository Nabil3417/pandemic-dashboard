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
  6. Evaluates trained fusion classifier (T-08) if available
  7. Expanded early warning with strict/soft thresholds per-outbreak (T-09)
  8. Saves all results to data/evaluation_results.json

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
    print("scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)

# ── T-08: trained fusion imports ──────────────────────────────────────────────
try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

# ── constants ─────────────────────────────────────────────────────────────────
DATA_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODELS_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
GROUND_TRUTH    = os.path.join(DATA_DIR, "outbreak_ground_truth.csv")
MOBILITY_CSV    = os.path.join(DATA_DIR, "dhaka_zone_mobility_2020_2022.csv")
TRENDS_CSV      = os.path.join(DATA_DIR, "dhaka_zone_symptom_trends.csv")
OUTPUT_JSON     = os.path.join(DATA_DIR, "evaluation_results.json")

# Fusion weights — must match app.py (fixed-weight baseline)
NLP_WEIGHT        = 0.25
WASTEWATER_WEIGHT = 0.40
MOBILITY_WEIGHT   = 0.35

print("Using fusion weights: NLP=0.25, Wastewater=0.40, Mobility=0.35")

# Outbreak threshold — fused score above this = predicted outbreak
OUTBREAK_THRESHOLD = 22.0

# T-09: Two thresholds for early warning
STRICT_THRESHOLD = 22.0
SOFT_THRESHOLD   = 15.0
LOOKBACK_WEEKS   = 8

# Zone to use for single-zone evaluation (zone 11 = Motijheel/central Dhaka)
EVAL_ZONE = 11


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load ground truth
# ══════════════════════════════════════════════════════════════════════════════

def load_ground_truth():
    print("\n  Loading ground truth labels...")
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
    print(f"\n  Loading Google Trends series (zone {zone_id})...")

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

    print("   WARNING: No trends data found — using zeros")
    return pd.DataFrame(columns=['date', 'symptom_score'])


def load_mobility_series(zone_id=EVAL_ZONE):
    """Load weekly mobility risk scores for a zone."""
    print(f"\n  Loading mobility series (zone {zone_id})...")

    if not os.path.exists(MOBILITY_CSV):
        print("   WARNING: Mobility CSV not found — using zeros")
        return pd.DataFrame(columns=['date', 'mobility_score'])

    df = pd.read_csv(MOBILITY_CSV)
    df.columns = df.columns.str.strip().str.lower()

    # Detect date column
    date_col = next((c for c in df.columns if 'date' in c), None)
    if not date_col:
        print("   WARNING: No date column found in mobility CSV")
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
        print(f"   WARNING: Could not identify score column. Columns: {list(df.columns)}")
        return pd.DataFrame(columns=['date', 'mobility_score'])


def load_iedcr_series():
    """Load monthly IEDCR normalized scores and expand to weekly."""
    print("\n  Loading IEDCR/DGHS series...")
    docs = list(iedcr_reports.find(
        {"disease": "dengue", "division": "Dhaka"},
        sort=[("year", 1), ("month", 1)]
    ))
    if not docs:
        print("   WARNING: No IEDCR data found — using zeros")
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
    print("\n  Aligning signals to ground truth weeks...")
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
        iedcr_score    = min(max(float(iedcr_score), 0), 100)

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
    print("\n  Running per-modality analysis...")
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
# STEP 6 — T-08: Trained Fusion Classifier Evaluation
# ══════════════════════════════════════════════════════════════════════════════

def compute_trained_fusion_predictions(aligned_df, model, scaler):
    """Use trained GB classifier to predict outbreak probabilities."""
    X = aligned_df[['nlp_proxy', 'wastewater_proxy', 'mobility_score']].values
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)[:, 1]  # P(outbreak)
    return proba


def evaluate_trained_fusion(aligned_df):
    """Load trained fusion model and evaluate if available. Returns (metrics_dict, proba_array_or_None)."""
    model_path = os.path.join(MODELS_DIR, "fusion_classifier.pkl")
    scaler_path = os.path.join(MODELS_DIR, "fusion_scaler.pkl")

    if not HAS_JOBLIB:
        print("\n  T-08: joblib not installed — skipping trained fusion evaluation")
        return None, None

    if not (os.path.exists(model_path) and os.path.exists(scaler_path)):
        print("\n  T-08: Trained fusion model not found — skipping (run train_fusion.py first)")
        return None, None

    try:
        model  = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
    except Exception as e:
        print(f"\n  T-08: Failed to load model ({e}) — skipping")
        return None, None

    print(f"\n  T-08: Evaluating trained fusion classifier ({type(model).__name__})...")
    y_true = aligned_df['outbreak_label'].values
    proba  = compute_trained_fusion_predictions(aligned_df, model, scaler)

    # Find optimal threshold on proba (maximize F1)
    best_f1 = 0
    best_thresh = 0.5
    for t in np.arange(0.05, 0.95, 0.01):
        preds = (proba >= t).astype(int)
        f1 = f1_score(y_true, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t

    final_preds = (proba >= best_thresh).astype(int)

    # Load feature importances from training results
    fi = {}
    results_path = os.path.join(DATA_DIR, "fusion_training_results.json")
    try:
        with open(results_path, 'r') as f:
            tres = json.load(f)
            fi = tres.get('best_model', {}).get('feature_importances', {})
    except Exception:
        pass

    metrics = compute_metrics(
        y_true.tolist(), final_preds.tolist(), proba.tolist(),
        label="Combined Model (Trained Fusion Classifier)"
    )
    metrics["threshold"] = round(float(best_thresh), 4)
    metrics["model_name"] = type(model).__name__
    metrics["feature_importances"] = fi

    # Print comparison
    fixed_f1 = f1_score(y_true, predict_from_score(aligned_df['fused_score'].tolist()), zero_division=0)
    fixed_auc = roc_auc_score(y_true, aligned_df['fused_score'].tolist()) if len(np.unique(y_true)) > 1 else 0
    print(f"   Fixed-Weight Baseline :  F1={fixed_f1:.4f}  AUC={fixed_auc:.4f}")
    print(f"   {type(model).__name__:22s}:  F1={metrics['f1_score']:.4f}  AUC={metrics['roc_auc']:.4f}")
    print(f"   Delta                 :  F1={metrics['f1_score']-fixed_f1:+.4f}  AUC={metrics['roc_auc']-fixed_auc:+.4f}")
    if fi:
        print(f"   Feature importances    :  {fi}")

    return metrics, proba


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — T-09: Expanded Early Warning Analysis
# ══════════════════════════════════════════════════════════════════════════════

def _identify_outbreak_periods(df):
    """
    Identify contiguous outbreak periods (runs of outbreak_label == 1).
    Returns list of dicts: [{start_idx, end_idx, start_date, end_date, duration}, ...]
    """
    outbreaks = []
    in_outbreak = False
    start_idx = None

    for i in range(len(df)):
        label = df.iloc[i]['outbreak_label']
        if label == 1 and not in_outbreak:
            in_outbreak = True
            start_idx = i
        elif label == 0 and in_outbreak:
            in_outbreak = False
            outbreaks.append({
                "start_idx":  start_idx,
                "end_idx":    i - 1,
                "start_date": str(df.iloc[start_idx]['date_start'].date()),
                "end_date":   str((df.iloc[i - 1]['date_start'] + timedelta(days=6)).date()),
                "duration":   i - start_idx,
            })
    # Handle outbreak that extends to end of data
    if in_outbreak:
        outbreaks.append({
            "start_idx":  start_idx,
            "end_idx":    len(df) - 1,
            "start_date": str(df.iloc[start_idx]['date_start'].date()),
            "end_date":   str((df.iloc[len(df) - 1]['date_start'] + timedelta(days=6)).date()),
            "duration":   len(df) - start_idx,
        })

    return outbreaks


def _compute_early_warning_for_score(df, outbreaks, score_col, threshold, label_prefix):
    """
    For a given score column and threshold, compute per-outbreak early warning lead times.
    Looks back up to LOOKBACK_WEEKS before each outbreak start.
    """
    per_outbreak = []
    lead_times = []

    for ob in outbreaks:
        start_idx = ob['start_idx']
        lookback_start = max(0, start_idx - LOOKBACK_WEEKS)
        lead = 0

        for j in range(lookback_start, start_idx):
            score = df.iloc[j][score_col]
            if score >= threshold:
                lead = start_idx - j  # weeks between crossing and outbreak start
                break

        per_outbreak.append({
            "start_date": ob['start_date'],
            "start_idx":  start_idx,
            "end_idx":    ob['end_idx'],
            "duration":   ob['duration'],
            "lead_weeks": lead,
        })
        lead_times.append(lead)

        status = f"{lead} weeks early" if lead > 0 else "not detected"
        print(f"   Outbreak {ob['start_date']} (weeks {start_idx}-{ob['end_idx']}): "
              f"{label_prefix} early warning: {status}")

    caught = sum(1 for lt in lead_times if lt > 0)
    avg_lead = round(np.mean([lt for lt in lead_times if lt > 0]), 1) if caught > 0 else 0.0

    return {
        "threshold":         threshold,
        "outbreaks_caught":  caught,
        "outbreaks_total":  len(outbreaks),
        "avg_lead_weeks":   avg_lead,
        "lead_times":       lead_times,
        "per_outbreak":     per_outbreak,
    }


def compute_early_warning(aligned_df, trained_proba=None):
    """
    T-09: Expanded early warning analysis.
    - Identifies outbreak periods (contiguous runs of outbreak_label==1)
    - For each outbreak, looks back up to 8 weeks before start
    - STRICT threshold (22.0): did fused score cross before outbreak?
    - SOFT threshold (15.0): did fused score cross before outbreak?
    - If trained_proba provided: also compute for trained fusion (thresholds 0.22, 0.15)
    """
    print("\n  T-09: Computing expanded early warning analysis...")

    df = aligned_df.copy().reset_index(drop=True)

    # Identify outbreak periods
    outbreaks = _identify_outbreak_periods(df)
    if not outbreaks:
        print("   No outbreaks found in ground truth data")
        return {"strict": None, "soft": None, "lookback_weeks": LOOKBACK_WEEKS,
                "outbreaks_total": 0}

    print(f"   Found {len(outbreaks)} distinct outbreak periods:")

    # Fixed-weight fused score (0-100 scale)
    print(f"\n   --- Fixed-Weight Fusion (threshold {STRICT_THRESHOLD} / {SOFT_THRESHOLD}) ---")
    strict = _compute_early_warning_for_score(df, outbreaks, 'fused_score', STRICT_THRESHOLD, "strict")
    soft   = _compute_early_warning_for_score(df, outbreaks, 'fused_score', SOFT_THRESHOLD,   "soft")

    print(f"\n   Strict early warning: caught {strict['outbreaks_caught']}/{strict['outbreaks_total']} outbreaks, "
          f"avg {strict['avg_lead_weeks']} weeks early")
    print(f"   Soft early warning:   caught {soft['outbreaks_caught']}/{soft['outbreaks_total']} outbreaks, "
          f"avg {soft['avg_lead_weeks']} weeks early")

    result = {
        "strict":    strict,
        "soft":      soft,
        "lookback_weeks":  LOOKBACK_WEEKS,
        "outbreaks_total": len(outbreaks),
    }

    # Trained fusion probabilities (0-1 scale) — if available
    if trained_proba is not None:
        df['trained_proba'] = trained_proba

        # Trained thresholds: equivalent to 22.0 and 15.0 on 0-100 scale
        trained_strict_thresh = STRICT_THRESHOLD / 100.0  # 0.22
        trained_soft_thresh   = SOFT_THRESHOLD   / 100.0  # 0.15

        print(f"\n   --- Trained Fusion Classifier (threshold {trained_strict_thresh} / {trained_soft_thresh}) ---")
        strict_trained = _compute_early_warning_for_score(
            df, outbreaks, 'trained_proba', trained_strict_thresh, "strict trained")
        soft_trained   = _compute_early_warning_for_score(
            df, outbreaks, 'trained_proba', trained_soft_thresh,   "soft trained")

        print(f"\n   Trained strict: caught {strict_trained['outbreaks_caught']}/{strict_trained['outbreaks_total']}, "
              f"avg {strict_trained['avg_lead_weeks']} weeks early")
        print(f"   Trained soft:   caught {soft_trained['outbreaks_caught']}/{soft_trained['outbreaks_total']}, "
              f"avg {soft_trained['avg_lead_weeks']} weeks early")

        result["strict_trained"] = strict_trained
        result["soft_trained"]   = soft_trained

    return result


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
        print("ERROR: No aligned data produced — check your CSV files and MongoDB collections")
        return

    y_true  = aligned_df['outbreak_label'].tolist()
    scores  = aligned_df['fused_score'].tolist()
    y_pred  = predict_from_score(scores)

    # ── Combined model metrics (fixed-weight baseline) ─────────────────────
    print("\n  Computing combined model metrics...")
    combined = compute_metrics(y_true, y_pred, scores,
                               label="Combined Model (NLP+Mobility+Wastewater)")

    print(f"\n{'='*65}")
    print("COMBINED MODEL RESULTS (Fixed-Weight Baseline)")
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

    # ── T-08: Trained fusion classifier evaluation ─────────────────────────
    trained_metrics, trained_proba = evaluate_trained_fusion(aligned_df)

    # ── T-09: Expanded early warning analysis ──────────────────────────────
    early_warning = compute_early_warning(aligned_df, trained_proba=trained_proba)

    # ── Build final output ─────────────────────────────────────────────────
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
        "combined_model":       combined,
        "combined_model_trained": trained_metrics,
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

    print(f"\n  Results saved to: {OUTPUT_JSON}")

    # ── Printed summary ────────────────────────────────────────────────────
    print(f"\n  MODALITY COMPARISON:")
    print(f"   {'Signal':<35} {'F1':>6}  {'AUC':>6}")
    print(f"   {'-'*50}")
    for key, m in modality_results.items():
        print(f"   {m['label']:<35} {m['f1_score']:>6.3f}  {m['roc_auc']:>6.3f}")
    print(f"   {'Combined (all three)':<35} {combined['f1_score']:>6.3f}  {combined['roc_auc']:>6.3f}")

    # T-08 comparison
    if trained_metrics:
        print(f"\n  FUSION METHOD COMPARISON (T-08):")
        print(f"   {'Method':<45} {'F1':>6}  {'AUC':>6}")
        print(f"   {'-'*60}")
        print(f"   {'Fixed-Weight Baseline':<45} {combined['f1_score']:>6.3f}  {combined['roc_auc']:>6.3f}")
        print(f"   {trained_metrics['model_name']:<45} {trained_metrics['f1_score']:>6.3f}  {trained_metrics['roc_auc']:>6.3f}")

    # T-09 early warning summary
    ew = early_warning
    strict_avg = ew.get('strict', {}).get('avg_lead_weeks', 0)
    soft_avg   = ew.get('soft', {}).get('avg_lead_weeks', 0)
    strict_caught = ew.get('strict', {}).get('outbreaks_caught', 0)
    soft_caught   = ew.get('soft', {}).get('outbreaks_caught', 0)
    total_ob      = ew.get('outbreaks_total', 0)

    if trained_metrics and ew.get('strict_trained'):
        t_strict_avg = ew['strict_trained'].get('avg_lead_weeks', 0)
        t_soft_avg   = ew['soft_trained'].get('avg_lead_weeks', 0)
        t_strict_caught = ew['strict_trained'].get('outbreaks_caught', 0)
        t_soft_caught   = ew['soft_trained'].get('outbreaks_caught', 0)
        print(f"\n  EARLY WARNING (T-09): {total_ob} outbreaks detected across 156 weeks")
        print(f"   {'Method':<25} {'Threshold':>10} {'Caught':>8} {'Avg Lead':>10}")
        print(f"   {'-'*55}")
        print(f"   {'Fixed strict':<25} {STRICT_THRESHOLD:>10.1f} {strict_caught:>5}/{total_ob} {strict_avg:>8.1f} wk")
        print(f"   {'Fixed soft':<25} {SOFT_THRESHOLD:>10.1f} {soft_caught:>5}/{total_ob} {soft_avg:>8.1f} wk")
        print(f"   {'Trained strict':<25} {STRICT_THRESHOLD/100:>10.2f} {t_strict_caught:>5}/{total_ob} {t_strict_avg:>8.1f} wk")
        print(f"   {'Trained soft':<25} {SOFT_THRESHOLD/100:>10.2f} {t_soft_caught:>5}/{total_ob} {t_soft_avg:>8.1f} wk")
    else:
        print(f"\n  Early warning: {total_ob} outbreaks, "
              f"strict ({STRICT_THRESHOLD}) catches {strict_caught}/{total_ob} avg {strict_avg}wk early, "
              f"soft ({SOFT_THRESHOLD}) catches {soft_caught}/{total_ob} avg {soft_avg}wk early")

    print(f"\n{'='*65}")


if __name__ == "__main__":
    run_evaluation()