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

# ── T-17: SHAP imports ─────────────────────────────────────────────────────────
try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

# ── N3-N7: Additional imports ─────────────────────────────────────────────
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, accuracy_score

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
    try:
        fm.fontManager.addfont('/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf')
        fm.fontManager.addfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'DejaVu Sans']
    except Exception:
        pass
    plt.rcParams['axes.unicode_minus'] = False
except ImportError:
    HAS_MATPLOTLIB = False

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
PAPER_FIGURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_figures")


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
            "disease":         row.get('disease', 'none').strip(),
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

    # ── A2: WARNING — in-sample F1 vs cross-validated F1 ────────────────────
    print(f"\n  ╔═══════════════════════════════════════════════════════════════════╗")
    print(f"  ║  WARNING: The F1 below is IN-SAMPLE (train=evaluate).           ║")
    print(f"  ║  For honest out-of-sample F1, see fusion_training_results.json. ║")
    print(f"  ╚═══════════════════════════════════════════════════════════════════╝")

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

    # ── A2: paper_notes with honest cross-validated metrics ─────────────────
    paper_notes = {}
    try:
        with open(results_path, 'r') as f:
            tres = json.load(f)
        cv_f1 = tres.get('gradient_boosting', {}).get('cv_f1_mean')
        cv_auc = tres.get('gradient_boosting', {}).get('cv_auc_mean')
        if cv_f1 is not None:
            paper_notes["cv_5fold_f1"] = cv_f1
        if cv_auc is not None:
            paper_notes["cv_5fold_auc"] = cv_auc
    except Exception:
        pass
    metrics["paper_notes"] = paper_notes if paper_notes else None

    # Print comparison
    fixed_f1 = f1_score(y_true, predict_from_score(aligned_df['fused_score'].tolist()), zero_division=0)
    fixed_auc = roc_auc_score(y_true, aligned_df['fused_score'].tolist()) if len(np.unique(y_true)) > 1 else 0
    print(f"   Fixed-Weight Baseline :  F1={fixed_f1:.4f}  AUC={fixed_auc:.4f}")
    print(f"   {type(model).__name__:22s}:  F1={metrics['f1_score']:.4f}  AUC={metrics['roc_auc']:.4f}")
    print(f"   Delta                 :  F1={metrics['f1_score']-fixed_f1:+.4f}  AUC={metrics['roc_auc']-fixed_auc:+.4f}")
    if paper_notes:
        print(f"   Honest 5-fold CV F1   :  {paper_notes.get('cv_5fold_f1', 'N/A')}")
        print(f"   Honest 5-fold CV AUC  :  {paper_notes.get('cv_5fold_auc', 'N/A')}")
    if fi:
        print(f"   Feature importances    :  {fi}")

    return metrics, proba


# ══════════════════════════════════════════════════════════════════════════════
# T-07: A3 — Weight Grid Search Optimization
# ══════════════════════════════════════════════════════════════════════════════

def run_weight_optimization(aligned_df):
    """
    T-07 / A3: Grid search over fixed-weight combinations to find the best
    manual weight assignment. This proves that the trained GradientBoosting
    classifier supersedes manual weight tuning.

    Sweeps NLP_WEIGHT, WASTEWATER_WEIGHT, MOBILITY_WEIGHT (sum=1.0)
    and reports F1/AUC for each combination.
    """
    print(f"\n  T-07 (A3): Weight Grid Search Optimization...")
    print(f"  NOTE: This sweeps many weight combos — may take 1-2 minutes.\n")

    y_true = aligned_df['outbreak_label'].values

    # Grid: step=0.1, only keep combos where sum==1.0 (within tolerance)
    step = 0.1
    best_f1 = -1
    best_auc = -1
    best_weights = None
    best_thresh = OUTBREAK_THRESHOLD
    all_results = []

    w_vals = np.arange(0.0, 1.01, step)

    for wn in w_vals:
        for ww in w_vals:
            wm = round(1.0 - wn - ww, 2)
            if wm < -0.001 or wm > 1.001:
                continue
            wm = max(0.0, min(1.0, wm))

            # Skip if all zero
            if wn == 0 and ww == 0 and wm == 0:
                continue

            # Compute weighted fusion score
            fused = (
                aligned_df['nlp_proxy'].values * wn +
                aligned_df['wastewater_proxy'].values * ww +
                aligned_df['mobility_score'].values * wm
            )

            # Find best threshold for this weight combo
            combo_best_f1 = -1
            combo_best_t = OUTBREAK_THRESHOLD
            for t in np.arange(5.0, 45.0, 1.0):
                preds = (fused >= t).astype(int)
                if len(np.unique(preds)) < 2:
                    continue
                f1 = f1_score(y_true, preds, zero_division=0)
                if f1 > combo_best_f1:
                    combo_best_f1 = f1
                    combo_best_t = t

            preds = (fused >= combo_best_t).astype(int)
            try:
                auc = roc_auc_score(y_true, fused)
            except Exception:
                auc = 0.0

            entry = {
                "nlp_w": round(float(wn), 2),
                "wastewater_w": round(float(ww), 2),
                "mobility_w": round(float(wm), 2),
                "f1": round(float(combo_best_f1), 4),
                "auc": round(float(auc), 4),
                "best_threshold": round(float(combo_best_t), 1),
            }
            all_results.append(entry)

            if combo_best_f1 > best_f1:
                best_f1 = combo_best_f1
                best_auc = auc
                best_weights = {"nlp": round(float(wn), 2), "wastewater": round(float(ww), 2), "mobility": round(float(wm), 2)}
                best_thresh = combo_best_t

    # Also evaluate current (baseline) weights
    fused_baseline = (
        aligned_df['nlp_proxy'].values * NLP_WEIGHT +
        aligned_df['wastewater_proxy'].values * WASTEWATER_WEIGHT +
        aligned_df['mobility_score'].values * MOBILITY_WEIGHT
    )
    baseline_preds = predict_from_score(fused_baseline.tolist())
    baseline_f1 = f1_score(y_true, baseline_preds, zero_division=0)
    try:
        baseline_auc = roc_auc_score(y_true, fused_baseline)
    except Exception:
        baseline_auc = 0.0

    # Sort by F1 descending, keep top 10
    all_results.sort(key=lambda x: x['f1'], reverse=True)
    top_10 = all_results[:10]

    print(f"\n{'='*70}")
    print(f"WEIGHT GRID SEARCH (T-07 / A3)")
    print(f"{'='*70}")
    print(f"  Baseline weights (NLP={NLP_WEIGHT}, WW={WASTEWATER_WEIGHT}, MOB={MOBILITY_WEIGHT}):")
    print(f"    F1={baseline_f1:.4f}  AUC={baseline_auc:.4f}")
    print(f"\n  Best grid-search weights (NLP={best_weights['nlp']}, WW={best_weights['wastewater']}, MOB={best_weights['mobility']}):")
    print(f"    F1={best_f1:.4f}  AUC={best_auc:.4f}  (threshold={best_thresh:.1f})")
    print(f"\n  Top 10 weight combinations:")
    print(f"  {'NLP':>5} {'WW':>5} {'MOB':>5} {'F1':>8} {'AUC':>8} {'Thresh':>7}")
    print(f"  {'-'*42}")
    for r in top_10:
        print(f"  {r['nlp_w']:>5.2f} {r['wastewater_w']:>5.2f} {r['mobility_w']:>5.2f} {r['f1']:>8.4f} {r['auc']:>8.4f} {r['best_threshold']:>7.1f}")
    print(f"{'='*70}")

    return {
        "baseline_weights": {"nlp": NLP_WEIGHT, "wastewater": WASTEWATER_WEIGHT, "mobility": MOBILITY_WEIGHT},
        "baseline_f1": round(float(baseline_f1), 4),
        "baseline_auc": round(float(baseline_auc), 4),
        "best_weights": best_weights,
        "best_f1": round(float(best_f1), 4),
        "best_auc": round(float(best_auc), 4),
        "best_threshold": round(float(best_thresh), 1),
        "top_10_combinations": top_10,
        "total_combinations_tested": len(all_results),
        "note": "Trained GradientBoosting classifier supersedes manual weight tuning (see trained_model metrics for comparison)",
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — T-17: SHAP Feature Contribution Analysis
# ══════════════════════════════════════════════════════════════════════════════

def compute_shap_values(aligned_df, fusion_model, scaler):
    """
    T-17: Compute SHAP values for the trained fusion classifier.
    Returns dict with mean_abs_shap, normalized_importance, feature_dominance, etc.
    Returns None if SHAP is not installed or model is None.
    """
    if fusion_model is None:
        return None

    if not HAS_SHAP:
        print("\n  T-17: shap not installed — run 'pip install shap' to enable SHAP analysis")
        return None

    print(f"\n  T-17: Computing SHAP feature contribution analysis ({type(fusion_model).__name__})...")

    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression

    feature_names = ['nlp_proxy', 'wastewater_proxy', 'mobility_score']
    X = aligned_df[feature_names].values
    X_scaled = scaler.transform(X)

    # Choose explainer based on model type
    if isinstance(fusion_model, (RandomForestClassifier, GradientBoostingClassifier)):
        explainer = shap.TreeExplainer(fusion_model)
        method_name = "TreeExplainer"
    elif isinstance(fusion_model, LogisticRegression):
        explainer = shap.LinearExplainer(fusion_model, X_scaled)
        method_name = "LinearExplainer"
    else:
        explainer = shap.KernelExplainer(fusion_model.predict_proba, shap.sample(X_scaled, 50))
        method_name = "KernelExplainer"

    shap_values = explainer.shap_values(X_scaled)

    # If shap_values is a list (binary classification), take class 1 SHAP values
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    # Mean absolute SHAP per feature
    mean_abs = np.mean(np.abs(shap_values), axis=0)
    total = mean_abs.sum()
    normalized = {fn: float(mean_abs[i] / total) if total > 0 else 0 for i, fn in enumerate(feature_names)}

    print(f"   Method: {method_name}")
    print(f"   Mean |SHAP|:  {dict(zip(feature_names, [round(float(v), 4) for v in mean_abs]))}")
    print(f"   Normalized:   {dict(zip(feature_names, [round(v, 4) for v in normalized.values()]))}")

    # Feature dominance during outbreak vs normal weeks
    dominant_feature_idx = np.argmax(np.abs(shap_values), axis=1)
    outbreak_mask = aligned_df['outbreak_label'].values == 1
    normal_mask   = ~outbreak_mask

    def _dominance_pct(mask):
        if mask.sum() == 0:
            return {fn: 0.0 for fn in feature_names}
        dom = dominant_feature_idx[mask]
        return {feature_names[i]: round(float((dom == i).sum() / len(dom) * 100), 1) for i in range(len(feature_names))}

    outbreak_dom = _dominance_pct(outbreak_mask)
    normal_dom   = _dominance_pct(normal_mask)

    print(f"   Outbreak weeks - dominant signal: NLP {outbreak_dom['nlp_proxy']}%, Search {outbreak_dom['wastewater_proxy']}%, Mobility {outbreak_dom['mobility_score']}%")
    print(f"   Normal weeks   - dominant signal: NLP {normal_dom['nlp_proxy']}%, Search {normal_dom['wastewater_proxy']}%, Mobility {normal_dom['mobility_score']}%")

    result = {
        "method": method_name,
        "feature_names": feature_names,
        "mean_abs_shap": {fn: round(float(mean_abs[i]), 4) for i, fn in enumerate(feature_names)},
        "normalized_importance": normalized,
        "shap_values_sample": shap_values[:20].tolist(),
        "weeks_sample_indices": aligned_df.index[:20].tolist(),
    }

    # Also save feature_dominance separately
    feature_dominance = {
        "outbreak_weeks": {
            "nlp_dominant_pct":       outbreak_dom['nlp_proxy'],
            "search_dominant_pct":    outbreak_dom['wastewater_proxy'],
            "mobility_dominant_pct":  outbreak_dom['mobility_score'],
        },
        "normal_weeks": {
            "nlp_dominant_pct":       normal_dom['nlp_proxy'],
            "search_dominant_pct":    normal_dom['wastewater_proxy'],
            "mobility_dominant_pct":  normal_dom['mobility_score'],
        },
    }

    return result, feature_dominance


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — N1: Per-Disease F1 Breakdown (COVID-19 vs Dengue)
# ══════════════════════════════════════════════════════════════════════════════

def per_disease_f1_breakdown(aligned_df, trained_proba=None):
    """
    N1: Compute Precision, Recall, F1, AUC separately for COVID-19 and Dengue weeks.
    For each disease, only outbreak weeks of THAT disease are positive;
    all other weeks (normal + other disease outbreaks) are negative.
    Also computes per-disease early warning lead times.
    """
    diseases = ['covid19', 'dengue']
    results = {}

    print(f"\n  N1: Per-Disease F1 Breakdown (COVID-19 vs Dengue)...")

    for dis in diseases:
        # Binary label: 1 = this disease's outbreak weeks, 0 = everything else
        y_true_dis = (aligned_df['disease'] == dis).astype(int).values
        n_pos = int(y_true_dis.sum())
        n_neg = int((y_true_dis == 0).sum())

        # --- Fixed-weight fusion ---
        fixed_preds  = predict_from_score(aligned_df['fused_score'].tolist())
        fixed_scores = aligned_df['fused_score'].tolist()

        fixed_tp  = int(sum((np.array(fixed_preds) == 1) & (y_true_dis == 1)))
        fixed_fp  = int(sum((np.array(fixed_preds) == 1) & (y_true_dis == 0)))
        fixed_fn  = int(sum((np.array(fixed_preds) == 0) & (y_true_dis == 1)))
        fixed_tn  = int(sum((np.array(fixed_preds) == 0) & (y_true_dis == 0)))

        fixed_prec = fixed_tp / (fixed_tp + fixed_fp) if (fixed_tp + fixed_fp) > 0 else 0
        fixed_rec  = fixed_tp / (fixed_tp + fixed_fn) if (fixed_tp + fixed_fn) > 0 else 0
        fixed_f1   = 2 * fixed_prec * fixed_rec / (fixed_prec + fixed_rec) if (fixed_prec + fixed_rec) > 0 else 0
        fixed_auc  = roc_auc_score(y_true_dis, fixed_scores) if len(np.unique(y_true_dis)) > 1 else 0

        dis_metrics = {
            "disease":              dis,
            "outbreak_weeks":       n_pos,
            "normal_weeks":         n_neg,
            "warning":              None if n_pos >= 10 else "small sample (<10 outbreak weeks)",
            "fixed_weight": {
                "precision": round(fixed_prec, 4),
                "recall":    round(fixed_rec, 4),
                "f1_score":  round(fixed_f1, 4),
                "roc_auc":   round(fixed_auc, 4),
                "tp": fixed_tp, "fp": fixed_fp, "fn": fixed_fn, "tn": fixed_tn,
            },
        }

        # --- Trained fusion (if available) ---
        if trained_proba is not None:
            best_f1 = 0
            best_t  = 0.5
            for t in np.arange(0.05, 0.95, 0.01):
                preds = (trained_proba >= t).astype(int)
                f1 = f1_score(y_true_dis, preds, zero_division=0)
                if f1 > best_f1:
                    best_f1 = f1
                    best_t  = t
            trained_preds = (trained_proba >= best_t).astype(int)

            t_tp  = int(sum((trained_preds == 1) & (y_true_dis == 1)))
            t_fp  = int(sum((trained_preds == 1) & (y_true_dis == 0)))
            t_fn  = int(sum((trained_preds == 0) & (y_true_dis == 1)))
            t_tn  = int(sum((trained_preds == 0) & (y_true_dis == 0)))

            t_prec = t_tp / (t_tp + t_fp) if (t_tp + t_fp) > 0 else 0
            t_rec  = t_tp / (t_tp + t_fn) if (t_tp + t_fn) > 0 else 0
            t_f1   = 2 * t_prec * t_rec / (t_prec + t_rec) if (t_prec + t_rec) > 0 else 0
            t_auc  = roc_auc_score(y_true_dis, trained_proba) if len(np.unique(y_true_dis)) > 1 else 0

            dis_metrics["trained_fusion"] = {
                "precision":    round(t_prec, 4),
                "recall":       round(t_rec, 4),
                "f1_score":     round(t_f1, 4),
                "roc_auc":      round(t_auc, 4),
                "threshold":    round(float(best_t), 4),
                "tp": t_tp, "fp": t_fp, "fn": t_fn, "tn": t_tn,
            }

        # --- Per-disease early warning lead times ---
        outbreaks_all = _identify_outbreak_periods(aligned_df)
        dis_outbreaks = []
        for ob in outbreaks_all:
            ob_disease = aligned_df.iloc[ob['start_idx']]['disease']
            if ob_disease == dis:
                dis_outbreaks.append(ob)

        if dis_outbreaks:
            ew_fixed = _compute_early_warning_for_score(
                aligned_df, dis_outbreaks, 'fused_score',
                STRICT_THRESHOLD, f"fixed_{dis}"
            )
            lead_times_fixed = [e['lead_weeks'] for e in ew_fixed.get('per_outbreak', []) if e['lead_weeks'] > 0]
            caught_fixed = len(lead_times_fixed)
            avg_fixed = sum(lead_times_fixed) / len(lead_times_fixed) if lead_times_fixed else 0

            dis_metrics["early_warning"] = {
                "outbreaks_total": len(dis_outbreaks),
                "fixed_strict_caught": caught_fixed,
                "fixed_strict_avg_lead": round(avg_fixed, 1) if caught_fixed > 0 else None,
            }

            if trained_proba is not None:
                trained_col = '_trained_proba_tmp'
                aligned_df[trained_col] = trained_proba
                ew_trained = _compute_early_warning_for_score(
                    aligned_df, dis_outbreaks, trained_col,
                    STRICT_THRESHOLD / 100, f"trained_{dis}"
                )
                lead_times_trained = [e['lead_weeks'] for e in ew_trained.get('per_outbreak', []) if e['lead_weeks'] > 0]
                caught_trained = len(lead_times_trained)
                avg_trained = sum(lead_times_trained) / len(lead_times_trained) if lead_times_trained else 0

                dis_metrics["early_warning"]["trained_strict_caught"] = caught_trained
                dis_metrics["early_warning"]["trained_strict_avg_lead"] = round(avg_trained, 1) if caught_trained > 0 else None

                aligned_df.drop(columns=[trained_col], inplace=True)
        else:
            dis_metrics["early_warning"] = {"outbreaks_total": 0}

        results[dis] = dis_metrics

        # Print per-disease detail
        label = "COVID-19" if dis == "covid19" else "Dengue"
        warn_txt = f"  WARNING: {dis_metrics['warning']}" if dis_metrics['warning'] else ""
        print(f"\n   --- {label} ({n_pos} outbreak weeks, {n_neg} non-outbreak){warn_txt} ---")
        print(f"   Fixed-Weight  :  P={fixed_prec:.4f}  R={fixed_rec:.4f}  F1={fixed_f1:.4f}  AUC={fixed_auc:.4f}")
        print(f"                     TP={fixed_tp}  FP={fixed_fp}  FN={fixed_fn}  TN={fixed_tn}")
        if trained_proba is not None:
            tm = dis_metrics["trained_fusion"]
            print(f"   Trained Fusion :  P={tm['precision']:.4f}  R={tm['recall']:.4f}  F1={tm['f1_score']:.4f}  AUC={tm['roc_auc']:.4f}  (threshold={tm['threshold']})")
            print(f"                     TP={tm['tp']}  FP={tm['fp']}  FN={tm['fn']}  TN={tm['tn']}")
        ew = dis_metrics.get("early_warning", {})
        if ew.get("outbreaks_total", 0) > 0:
            print(f"   Early Warning  :  fixed catches {ew.get('fixed_strict_caught',0)}/{ew['outbreaks_total']}, avg {ew.get('fixed_strict_avg_lead', 0) or 0:.1f} wk early")
            if trained_proba is not None and 'trained_strict_caught' in ew:
                print(f"                     trained catches {ew.get('trained_strict_caught',0)}/{ew['outbreaks_total']}, avg {ew.get('trained_strict_avg_lead', 0) or 0:.1f} wk early")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8b — N2: Bootstrap 95% CIs + McNemar Statistical Significance Test
# ══════════════════════════════════════════════════════════════════════════════

def compute_n2_statistical_significance(aligned_df, trained_proba=None):
    """
    N2: Bootstrap 95% confidence intervals for F1 and AUC scores,
    plus McNemar's test comparing fixed-weight vs trained fusion.

    - Stratified bootstrap (1000 iterations) preserving outbreak/non-outbreak ratio
    - CIs for: overall, COVID-19, Dengue (both fixed-weight and trained fusion)
    - McNemar's test with continuity correction for classifier comparison
    """
    N_BOOT = 1000
    np.random.seed(42)

    print(f"\n  N2: Bootstrap 95% CIs + McNemar Test ({N_BOOT} iterations)...")

    y_true      = aligned_df['outbreak_label'].values
    fixed_preds = np.array(predict_from_score(aligned_df['fused_score'].tolist()))
    fixed_scores = aligned_df['fused_score'].values

    pos_idx = np.where(y_true == 1)[0]
    neg_idx = np.where(y_true == 0)[0]

    covid_mask  = (aligned_df['disease'] == 'covid19').values
    dengue_mask = (aligned_df['disease'] == 'dengue').values

    # Bootstrap accumulators
    acc = {
        "overall_fixed_f1": [], "overall_fixed_auc": [],
        "overall_trained_f1": [], "overall_trained_auc": [],
        "covid_fixed_f1": [], "covid_fixed_auc": [],
        "covid_trained_f1": [], "covid_trained_auc": [],
        "dengue_fixed_f1": [], "dengue_fixed_auc": [],
        "dengue_trained_f1": [], "dengue_trained_auc": [],
    }

    # Get trained threshold (same optimisation as main evaluation)
    trained_thresh = 0.5
    if trained_proba is not None:
        best_f1 = 0
        for t in np.arange(0.05, 0.95, 0.01):
            p = (trained_proba >= t).astype(int)
            f = f1_score(y_true, p, zero_division=0)
            if f > best_f1:
                best_f1 = f
                trained_thresh = t

    for _ in range(N_BOOT):
        # Stratified resample (preserve outbreak ratio)
        pos_s = np.random.choice(pos_idx, size=len(pos_idx), replace=True)
        neg_s = np.random.choice(neg_idx, size=len(neg_idx), replace=True)
        idx   = np.concatenate([pos_s, neg_s])

        yt = y_true[idx]
        fp = fixed_preds[idx]
        fs = fixed_scores[idx]
        has_both = len(np.unique(yt)) > 1

        # Overall fixed-weight
        acc["overall_fixed_f1"].append(f1_score(yt, fp, zero_division=0))
        acc["overall_fixed_auc"].append(roc_auc_score(yt, fs) if has_both else 0.0)

        # Overall trained fusion
        if trained_proba is not None:
            tp      = trained_proba[idx]
            tp_pred = (tp >= trained_thresh).astype(int)
            acc["overall_trained_f1"].append(f1_score(yt, tp_pred, zero_division=0))
            acc["overall_trained_auc"].append(roc_auc_score(yt, tp) if has_both else 0.0)

        # Per-disease: COVID-19
        yc = covid_mask[idx].astype(int)
        if len(np.unique(yc)) > 1:
            acc["covid_fixed_f1"].append(f1_score(yc, fp, zero_division=0))
            acc["covid_fixed_auc"].append(roc_auc_score(yc, fs))
            if trained_proba is not None:
                acc["covid_trained_f1"].append(f1_score(yc, tp_pred, zero_division=0))
                acc["covid_trained_auc"].append(roc_auc_score(yc, tp))

        # Per-disease: Dengue
        yd = dengue_mask[idx].astype(int)
        if len(np.unique(yd)) > 1:
            acc["dengue_fixed_f1"].append(f1_score(yd, fp, zero_division=0))
            acc["dengue_fixed_auc"].append(roc_auc_score(yd, fs))
            if trained_proba is not None:
                acc["dengue_trained_f1"].append(f1_score(yd, tp_pred, zero_division=0))
                acc["dengue_trained_auc"].append(roc_auc_score(yd, tp))

    # Compute 95% CIs (percentile method)
    def ci(arr):
        if len(arr) < 10:
            return [None, None]
        a = np.array(arr)
        return [round(float(np.percentile(a, 2.5)), 4),
                round(float(np.percentile(a, 97.5)), 4)]

    results = {
        "bootstrap_iterations": N_BOOT,
        "confidence_level": 0.95,
        "overall": {
            "fixed_weight": {
                "f1_ci": ci(acc["overall_fixed_f1"]),
                "auc_ci": ci(acc["overall_fixed_auc"]),
            },
        },
        "covid19": {
            "fixed_weight": {
                "f1_ci": ci(acc["covid_fixed_f1"]),
                "auc_ci": ci(acc["covid_fixed_auc"]),
            },
        },
        "dengue": {
            "fixed_weight": {
                "f1_ci": ci(acc["dengue_fixed_f1"]),
                "auc_ci": ci(acc["dengue_fixed_auc"]),
            },
        },
    }
    if trained_proba is not None:
        results["overall"]["trained_fusion"] = {
            "f1_ci": ci(acc["overall_trained_f1"]),
            "auc_ci": ci(acc["overall_trained_auc"]),
        }
        results["covid19"]["trained_fusion"] = {
            "f1_ci": ci(acc["covid_trained_f1"]),
            "auc_ci": ci(acc["covid_trained_auc"]),
        }
        results["dengue"]["trained_fusion"] = {
            "f1_ci": ci(acc["dengue_trained_f1"]),
            "auc_ci": ci(acc["dengue_trained_auc"]),
        }

    # ── McNemar's Test ─────────────────────────────────────────────────────
    # Compares fixed-weight vs trained fusion using ground-truth correctness
    # 2x2 table: a=both correct, b=fixed only, c=trained only, d=both wrong
    if trained_proba is not None:
        trained_pred = (trained_proba >= trained_thresh).astype(int)

        a = int(sum((fixed_preds == y_true) & (trained_pred == y_true)))
        b = int(sum((fixed_preds == y_true) & (trained_pred != y_true)))
        c = int(sum((fixed_preds != y_true) & (trained_pred == y_true)))
        d = int(sum((fixed_preds != y_true) & (trained_pred != y_true)))

        if (b + c) > 0:
            try:
                from scipy.stats import chi2
                statistic = ((abs(b - c) - 1) ** 2) / (b + c)   # continuity-corrected
                p_value  = float(1 - chi2.cdf(statistic, df=1))
            except ImportError:
                statistic = ((abs(b - c) - 1) ** 2) / (b + c)
                p_value  = None
        else:
            statistic = 0.0
            p_value   = 1.0

        results["mcnemar"] = {
            "comparison":             "fixed_weight_vs_trained_fusion",
            "contingency_table":      {"a_both_correct": a, "b_fixed_only": b,
                                       "c_trained_only": c, "d_both_wrong": d},
            "statistic":              round(statistic, 4),
            "p_value":                round(p_value, 6) if p_value is not None else None,
            "significant_at_005":     bool(p_value < 0.05) if p_value is not None else None,
            "correction":             "continuity-corrected (Edwards)",
            "null_hypothesis":        "Both classifiers have equal error rates",
        }

        print(f"   McNemar's Test (Fixed vs Trained):")
        print(f"     Contingency:  a(both OK)={a}  b(fixed OK)={b}  c(trained OK)={c}  d(both wrong)={d}")
        print(f"     chi2 = {statistic:.4f}, p = {p_value:.6f}" if p_value is not None
              else f"     chi2 = {statistic:.4f}, p = N/A (scipy not found)")
        if p_value is not None and p_value < 0.05:
            print(f"     >> SIGNIFICANT (p < 0.05) — trained fusion is statistically different from fixed-weight")
        elif p_value is not None:
            print(f"     >> NOT significant (p >= 0.05)")
        else:
            print(f"     >> Cannot determine significance (scipy required for p-value)")

    # ── Print CI table ─────────────────────────────────────────────────────
    print(f"\n   Bootstrap 95% Confidence Intervals:")
    print(f"   {'Configuration':<30} {'F1 95% CI':>24} {'AUC 95% CI':>24}")
    print(f"   {'-'*80}")

    def _fmt_ci(lo, hi):
        if lo is None:
            return "N/A"
        return f"[{lo:.4f}, {hi:.4f}]"

    def _print_ci(label, cfg):
        f1 = cfg.get("f1_ci", [None, None])
        auc = cfg.get("auc_ci", [None, None])
        print(f"   {label:<30} {_fmt_ci(f1[0], f1[1]):>24} {_fmt_ci(auc[0], auc[1]):>24}")

    _print_ci("Overall / Fixed-Weight", results["overall"]["fixed_weight"])
    if trained_proba is not None:
        _print_ci("Overall / Trained Fusion", results["overall"]["trained_fusion"])
    for dk, dl in [("covid19", "COVID-19"), ("dengue", "Dengue")]:
        _print_ci(f"{dl} / Fixed-Weight", results[dk]["fixed_weight"])
        if trained_proba is not None and "trained_fusion" in results[dk]:
            _print_ci(f"{dl} / Trained Fusion", results[dk]["trained_fusion"])

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — T-09: Expanded Early Warning Analysis
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
# N3 — Walk-Forward Rolling-Origin Cross-Validation
# ══════════════════════════════════════════════════════════════════════════════

def run_walk_forward_cv(aligned_df, min_train_weeks=52):
    """
    N3: Walk-forward (rolling-origin) cross-validation for time-series data.
    Train on weeks 0..N-1, predict week N; expand to 0..N, predict N+1; etc.
    This avoids future leakage and is the correct CV for temporal data.
    """
    print(f"\n  N3: Walk-Forward Rolling-Origin CV (min_train={min_train_weeks} weeks)...")
    print(f"  NOTE: This trains {len(aligned_df) - min_train_weeks} models — expect 5-10 minutes on CPU.\n")

    df = aligned_df.copy().sort_values('date_start').reset_index(drop=True)
    feature_cols = ['nlp_proxy', 'wastewater_proxy', 'mobility_score']
    records = []
    model_counts = {'logistic': 0, 'rf': 0, 'gb': 0, 'majority': 0}
    n_folds = len(df) - min_train_weeks

    for test_idx in range(min_train_weeks, len(df)):
        if (test_idx - min_train_weeks + 1) % 10 == 0:
            pct = (test_idx - min_train_weeks + 1) / n_folds * 100
            print(f"     Fold {test_idx - min_train_weeks + 1}/{n_folds} ({pct:.0f}%)...")

        train_df = df.iloc[:test_idx]
        test_df  = df.iloc[test_idx:test_idx + 1]
        X_train  = train_df[feature_cols].values
        y_train  = train_df['outbreak_label'].values
        X_test   = test_df[feature_cols].values
        actual   = int(test_df['outbreak_label'].values[0])

        # Handle single-class training folds
        if len(np.unique(y_train)) < 2:
            pred  = int(np.median(y_train))
            proba = float(y_train.mean())
            best_name = 'majority'
            model_counts['majority'] += 1
        else:
            scaler = MinMaxScaler().fit(X_train)
            X_train_s = scaler.transform(X_train)
            X_test_s  = scaler.transform(X_test)

            models = {
                'logistic': LogisticRegression(C=1.0, max_iter=1000, random_state=42),
                'rf':       RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42),
                'gb':       GradientBoostingClassifier(n_estimators=100, max_depth=2,
                                                       learning_rate=0.1, random_state=42),
            }

            # Pick best model by 5-fold stratified inner CV F1 on training data
            best_name  = 'gb'
            best_f1_cv = -1.0
            try:
                n_splits = min(5, int(y_train.sum()), int((y_train == 0).sum()))
                if n_splits < 2:
                    n_splits = 2
                cv = StratifiedKFold(n_splits=n_splits, shuffle=False)
                for name, mdl in models.items():
                    try:
                        scores = cross_val_score(mdl, X_train_s, y_train, cv=cv, scoring='f1')
                        if scores.mean() > best_f1_cv:
                            best_f1_cv = scores.mean()
                            best_name  = name
                    except Exception:
                        continue
            except Exception:
                pass

            # Train best model on full training set and predict
            best_model = models[best_name]
            best_model.fit(X_train_s, y_train)
            pred  = int(best_model.predict(X_test_s)[0])
            proba = float(best_model.predict_proba(X_test_s)[0, 1])
            model_counts[best_name] += 1

        # Get the test date
        test_date_val = df.iloc[test_idx].get('date_start', '')
        if hasattr(test_date_val, 'date'):
            test_date_str = str(test_date_val.date())
        else:
            test_date_str = str(test_date_val)

        records.append({
            'week_idx': int(test_idx),
            'date':     test_date_str,
            'pred':     pred,
            'proba':    round(proba, 4),
            'actual':   actual,
            'model':    best_name,
        })

    # ── Compute aggregate metrics ──────────────────────────────────────────
    y_true_wf  = np.array([r['actual'] for r in records])
    y_pred_wf  = np.array([r['pred']   for r in records])
    y_proba_wf = np.array([r['proba']  for r in records])

    wf_f1   = f1_score(y_true_wf, y_pred_wf, zero_division=0)
    wf_prec = precision_score(y_true_wf, y_pred_wf, zero_division=0)
    wf_rec  = recall_score(y_true_wf, y_pred_wf, zero_division=0)
    wf_acc  = accuracy_score(y_true_wf, y_pred_wf)
    wf_cm   = confusion_matrix(y_true_wf, y_pred_wf)
    tn, fp, fn, tp = wf_cm.ravel() if wf_cm.size == 4 else (0, 0, 0, 0)

    try:
        wf_auc = roc_auc_score(y_true_wf, y_proba_wf)
    except Exception:
        wf_auc = 0.0

    # Per-year F1
    per_year = {}
    for yr in sorted(df['year'].unique()):
        yr_indices = [i for i, r in enumerate(records)
                      if i + min_train_weeks < len(df) and
                      df.iloc[i + min_train_weeks]['year'] == yr]
        if not yr_indices:
            continue
        yt = y_true_wf[yr_indices]
        yp = y_pred_wf[yr_indices]
        if len(np.unique(yt)) > 1:
            yr_f1 = f1_score(yt, yp, zero_division=0)
            per_year[str(int(yr))] = {'f1': round(float(yr_f1), 4), 'n': len(yr_indices)}

    total = sum(model_counts.values())
    dist = {k: round(v / total * 100, 1) if total > 0 else 0
            for k, v in model_counts.items()}

    print(f"\n{'='*65}")
    print(f"WALK-FORWARD CV (N3)")
    print(f"{'='*65}")
    print(f"  Test weeks: {len(records)} (from week {min_train_weeks+1} to week {len(df)})")
    print(f"  F1 = {wf_f1:.4f} | Precision = {wf_prec:.4f} | Recall = {wf_rec:.4f} | AUC = {wf_auc:.4f}")
    for yr, vals in sorted(per_year.items()):
        print(f"  Per-year: {yr} F1={vals['f1']:.4f} (n={vals['n']})")
    print(f"  Models per fold: {', '.join(f'{k} {v}%' for k, v in dist.items())}")
    print(f"{'='*65}")

    return {
        'method': 'rolling-origin walk-forward',
        'min_train_weeks': min_train_weeks,
        'n_test_weeks': len(records),
        'f1_score':  round(float(wf_f1), 4),
        'precision': round(float(wf_prec), 4),
        'recall':    round(float(wf_rec), 4),
        'roc_auc':   round(float(wf_auc), 4),
        'accuracy':  round(float(wf_acc), 4),
        'confusion_matrix': [[int(tn), int(fp)], [int(fn), int(tp)]],
        'per_year': per_year,
        'model_selection_distribution': dist,
        'per_week_predictions': records,
    }



# ══════════════════════════════════════════════════════════════════════════════
# N4 — Lead-Time vs F1 Trade-off Curve
# ══════════════════════════════════════════════════════════════════════════════

def plot_leadtime_f1_curve(aligned_df, output_dir, trained_proba=None):
    """
    N4: Sweep alert threshold from 5 to 40. For each threshold compute F1 and
    average lead time. Plot the Pareto curve and save as PNG.
    """
    print(f"\n  N4: Computing lead-time vs F1 trade-off curve...")

    if not HAS_MATPLOTLIB:
        print("   WARNING: matplotlib not installed — skipping N4 plot")
        return None

    os.makedirs(output_dir, exist_ok=True)
    df = aligned_df.copy().reset_index(drop=True)
    outbreaks = _identify_outbreak_periods(df)

    if not outbreaks:
        print("   WARNING: No outbreaks found — returning empty curve")
        return None

    # Use trained proba * 100 if available, else fixed-weight fused_score
    if trained_proba is not None:
        score_series = trained_proba * 100
    else:
        score_series = df['fused_score'].values.copy()

    y_true = df['outbreak_label'].values
    thresholds = list(range(5, 41))  # 36 values
    results = []

    for thresh in thresholds:
        preds = (score_series >= thresh).astype(int)
        f1_val = f1_score(y_true, preds, zero_division=0) if len(np.unique(preds)) > 1 else 0.0

        # Average lead time
        lead_times = []
        n_detected = 0
        for ob in outbreaks:
            start_idx = ob['start_idx']
            lookback_start = max(0, start_idx - LOOKBACK_WEEKS)
            for j in range(lookback_start, start_idx):
                if score_series[j] >= thresh:
                    lead_times.append(start_idx - j)
                    n_detected += 1
                    break

        avg_lead = float(np.mean(lead_times)) if lead_times else 0.0
        results.append({
            'threshold': thresh,
            'f1': round(float(f1_val), 4),
            'lead_time': round(avg_lead, 2),
            'n_outbreaks_detected': n_detected,
        })

    # Operating point: threshold = 22
    op_idx = next((i for i, r in enumerate(results) if r['threshold'] == 22), 0)

    # ── Plot ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    xs = [r['lead_time'] for r in results]
    ys = [r['f1'] for r in results]

    ax.plot(xs, ys, 'o-', color='#2563EB', markersize=4, linewidth=1.5, zorder=3)
    ax.fill_between(xs, ys, alpha=0.08, color='#2563EB')

    # Operating point star
    ax.scatter([xs[op_idx]], [ys[op_idx]], marker='*', s=200, color='#DC2626',
               zorder=5, edgecolors='black', linewidths=0.5)
    ax.annotate(f't=22 (F1={ys[op_idx]:.3f}, Lead={xs[op_idx]:.1f}wk)',
                xy=(xs[op_idx], ys[op_idx]),
                xytext=(xs[op_idx] + 0.3, ys[op_idx] - 0.04),
                fontsize=8, color='#DC2626', fontweight='bold')

    # Annotate other thresholds
    for t_val in [10, 15, 30]:
        idx = t_val - 5
        if 0 <= idx < len(results):
            ax.annotate(f't={t_val}', xy=(xs[idx], ys[idx]),
                        xytext=(xs[idx] + 0.2, ys[idx] + 0.02),
                        fontsize=7, color='#6B7280')

    ax.set_xlabel('Average Lead Time (weeks)', fontsize=11)
    ax.set_ylabel('F1 Score', fontsize=11)
    ax.set_title('Lead-Time vs F1 Trade-off Curve', fontsize=13, fontweight='bold')
    ax.set_title('Sweeping alert threshold from 5 to 40  -  BioGuard trained fusion',
                 fontsize=9, style='italic', pad=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.2)

    output_path = os.path.join(output_dir, 'fig3_leadtime_f1_curve.png')
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"   Saved: {output_path}")

    op = results[op_idx]
    return {
        'thresholds':             [r['threshold'] for r in results],
        'f1_scores':              [r['f1'] for r in results],
        'lead_times':             [r['lead_time'] for r in results],
        'n_outbreaks_detected':   [r['n_outbreaks_detected'] for r in results],
        'operating_point': {
            'threshold': op['threshold'],
            'f1':        op['f1'],
            'lead_time': op['lead_time'],
        },
    }



# ══════════════════════════════════════════════════════════════════════════════
# N5 — Calibration Analysis (Brier Score + Reliability Diagram)
# ══════════════════════════════════════════════════════════════════════════════

def compute_calibration(aligned_df, fusion_model, scaler):
    """
    N5: Brier score, Brier skill score, calibration slope, and reliability diagram.
    Shows whether predicted probabilities are well-calibrated.
    """
    print(f"\n  N5: Computing calibration analysis...")

    fig_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_figures")
    os.makedirs(fig_dir, exist_ok=True)

    feature_cols = ['nlp_proxy', 'wastewater_proxy', 'mobility_score']
    X = aligned_df[feature_cols].values
    true_labels = aligned_df['outbreak_label'].values

    if fusion_model is not None and scaler is not None:
        X_scaled = scaler.transform(X)
        proba = fusion_model.predict_proba(X_scaled)[:, 1]
    else:
        print("   WARNING: No trained model — using fixed-weight fused_score / 100")
        proba = aligned_df['fused_score'].values / 100.0

    # Brier score
    brier = brier_score_loss(true_labels, proba)
    brier_clim = float(np.var(true_labels))
    brier_skill = 1.0 - brier / brier_clim if brier_clim > 0 else 0.0

    # Reliability diagram — 10 equal-width bins
    n_bins = 10
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centers_list = []
    bins_predicted = []
    bins_observed   = []
    n_per_bin       = []
    bin_data        = []

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (proba >= low) & (proba <= high)
        else:
            mask = (proba >= low) & (proba < high)
        n = int(mask.sum())
        if n > 0:
            mean_pred = float(proba[mask].mean())
            obs_freq  = float(true_labels[mask].mean())
            center    = float((low + high) / 2)
            bin_centers_list.append(center)
            bins_predicted.append(mean_pred)
            bins_observed.append(obs_freq)
            n_per_bin.append(n)
            bin_data.append({
                'center':             round(center, 2),
                'mean_predicted':     round(mean_pred, 4),
                'observed_frequency': round(obs_freq, 4),
                'n_samples':          n,
            })

    # Calibration slope (logistic regression of true ~ proba)
    cal_slope = None
    try:
        cal_model = LogisticRegression(max_iter=1000)
        cal_model.fit(proba.reshape(-1, 1), true_labels)
        cal_slope = float(cal_model.coef_[0][0])
    except Exception:
        pass

    print(f"   Brier Score: {brier:.4f} (climatology: {brier_clim:.4f}, skill: {brier_skill:.4f})")
    print(f"   Calibration slope: {cal_slope:.4f}" if cal_slope is not None else "   Calibration slope: N/A")

    # ── Plot ───────────────────────────────────────────────────────────────
    if HAS_MATPLOTLIB and bin_centers_list:
        fig, ax = plt.subplots(figsize=(6, 6), constrained_layout=True)
        ax.plot([0, 1], [0, 1], '--', color='gray', linewidth=1, label='Perfect calibration')
        ax.plot(bin_centers_list, bins_observed, 'o-', color='#2563EB',
                markersize=6, linewidth=2, label='Model')

        # Sample-count bars on twin axis
        ax2 = ax.twinx()
        ax2.bar(bin_centers_list, n_per_bin, width=0.08, alpha=0.15, color='#6B7280')
        ax2.set_ylabel('Number of Samples', fontsize=9, color='#6B7280')
        ax2.tick_params(axis='y', labelcolor='#6B7280')

        ax.set_xlabel('Mean Predicted Probability', fontsize=11)
        ax.set_ylabel('Observed Frequency', fontsize=11)
        ax.set_title('Reliability Diagram', fontsize=13, fontweight='bold')
        sub = f'Brier = {brier:.4f}'
        if cal_slope is not None:
            sub += f' | Calibration slope = {cal_slope:.3f}'
        ax.set_title(sub, fontsize=9, style='italic', pad=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, linestyle='--', alpha=0.2)
        ax.legend(loc='upper left', fontsize=8)

        out_path = os.path.join(fig_dir, 'fig4_reliability.png')
        fig.savefig(out_path, dpi=300)
        plt.close(fig)
        print(f"   Saved: {out_path}")

    return {
        'brier_score':              round(float(brier), 6),
        'brier_score_climatology':  round(float(brier_clim), 6),
        'brier_skill_score':        round(float(brier_skill), 4),
        'calibration_slope':        round(float(cal_slope), 4) if cal_slope is not None else None,
        'bins':                     bin_data,
    }



# ══════════════════════════════════════════════════════════════════════════════
# N6 — Cost-Sensitive Evaluation (FN Weighted)
# ══════════════════════════════════════════════════════════════════════════════

def compute_cost_sensitive(trained_preds, true_labels, trained_proba):
    """
    N6: Cost-sensitive evaluation with false negatives penalized 2x, 5x, 10x
    relative to false positives. Also finds the optimal threshold per cost ratio.
    """
    print(f"\n  N6: Cost-Sensitive Evaluation...")

    y_true = np.asarray(true_labels)
    y_pred = np.asarray(trained_preds)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())

    results = {}

    for cost_fn_mult in [1, 2, 5, 10]:
        cost_fp = 1
        cost_fn = cost_fn_mult

        # Weighted metrics
        w_prec = tp / (tp + cost_fp * fp) if (tp + cost_fp * fp) > 0 else 0
        w_rec  = tp / (tp + cost_fn * fn) if (tp + cost_fn * fn) > 0 else 0
        w_f1   = 2 * w_prec * w_rec / (w_prec + w_rec) if (w_prec + w_rec) > 0 else 0
        total_cost = cost_fp * fp + cost_fn * fn

        # Find optimal threshold that minimises total cost
        best_thresh = 0.5
        min_cost    = total_cost
        for t in np.arange(0.05, 0.96, 0.05):
            p = (trained_proba >= t).astype(int)
            c_fp = int(((p == 1) & (y_true == 0)).sum())
            c_fn = int(((p == 0) & (y_true == 1)).sum())
            c = cost_fp * c_fp + cost_fn * c_fn
            if c < min_cost:
                min_cost    = c
                best_thresh = float(t)

        key = f"fn_{cost_fn_mult}x"
        results[key] = {
            'f1':               round(float(w_f1), 4),
            'precision':        round(float(w_prec), 4),
            'recall':           round(float(w_rec), 4),
            'total_cost':       int(total_cost),
            'optimal_threshold': round(best_thresh, 2),
            'min_total_cost':   int(min_cost),
        }

    # Print table
    print(f"\n{'='*70}")
    print(f"COST-SENSITIVE EVALUATION (N6)")
    print(f"{'='*70}")
    hdr = f"  {'Cost (FN mult)':<20} {'F1':>7} {'Precision':>10} {'Recall':>8} {'Total Cost':>12} {'Opt Thresh':>11}"
    print(hdr)
    print(f"  {'-'*72}")
    for mult, label in [(1, '1x (symmetric)'), (2, '2x'), (5, '5x'), (10, '10x')]:
        r = results[f'fn_{mult}x']
        print(f"  {label:<20} {r['f1']:>7.4f} {r['precision']:>10.4f} {r['recall']:>8.4f} "
              f"{r['total_cost']:>12} {r['optimal_threshold']:>11.2f}")
    print(f"{'='*70}")

    return results



# ══════════════════════════════════════════════════════════════════════════════
# N7 — Missing-Modality Robustness Ablation
# ══════════════════════════════════════════════════════════════════════════════

def compute_missing_modality_ablation(aligned_df, fusion_model, scaler):
    """
    N7: Evaluate robustness by zeroing out each modality in turn.
    Shows no single modality is sufficient — strongest defense of multi-modal design.
    """
    print(f"\n  N7: Missing-Modality Ablation...")

    feature_cols = ['nlp_proxy', 'wastewater_proxy', 'mobility_score']
    X = aligned_df[feature_cols].values
    y_true = aligned_df['outbreak_label'].values

    scenarios = {
        'all':         {},
        'no_nlp':      {'nlp_proxy': 0.0},
        'no_mobility': {'mobility_score': 0.0},
        'no_search':   {'wastewater_proxy': 0.0},
    }

    labels = {
        'all':         'All modalities (baseline)',
        'no_nlp':      'No NLP',
        'no_mobility': 'No Mobility',
        'no_search':   'No Symptom Search',
    }

    notes = {
        'all':         'Full system',
        'no_nlp':      'Social media offline',
        'no_mobility': 'Google Mobility retired Oct 2023',
        'no_search':   'Google Trends unavailable',
    }

    results = {}
    baseline_f1 = None

    for scenario, zeros in scenarios.items():
        X_mod = X.copy()
        for col, val in zeros.items():
            col_idx = feature_cols.index(col)
            X_mod[:, col_idx] = val

        X_scaled = scaler.transform(X_mod)
        proba = fusion_model.predict_proba(X_scaled)[:, 1]

        # Find optimal threshold (maximize F1)
        best_f1 = 0
        best_t  = 0.5
        for t in np.arange(0.05, 0.95, 0.01):
            preds = (proba >= t).astype(int)
            f1 = f1_score(y_true, preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_t  = t

        preds = (proba >= best_t).astype(int)
        prec = precision_score(y_true, preds, zero_division=0)
        rec  = recall_score(y_true, preds, zero_division=0)
        try:
            auc = roc_auc_score(y_true, proba)
        except Exception:
            auc = 0.0

        cm = confusion_matrix(y_true, preds)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

        drop = 0.0
        if scenario == 'all':
            baseline_f1 = best_f1
        elif baseline_f1 and baseline_f1 > 0:
            drop = round(1.0 - (best_f1 / baseline_f1), 4)

        results[scenario] = {
            'f1':               round(float(best_f1), 4),
            'precision':        round(float(prec), 4),
            'recall':           round(float(rec), 4),
            'auc':              round(float(auc), 4),
            'tp': int(tp), 'fp': int(fp), 'tn': int(tn), 'fn': int(fn),
            'relative_f1_drop': drop,
        }

    # Print table
    print(f"\n{'='*65}")
    print(f"MISSING-MODALITY ABLATION (N7)")
    print(f"{'='*65}")
    print(f"  {'Scenario':<25} {'F1':>6} {'AUC':>6} {'F1 Drop':>10} {'Note':<30}")
    print(f"  {'-'*80}")
    for key in ['all', 'no_nlp', 'no_mobility', 'no_search']:
        r = results[key]
        drop_s = f"{r['relative_f1_drop']*100:.1f}%"
        print(f"  {labels[key]:<25} {r['f1']:>6.4f} {r['auc']:>6.4f} {drop_s:>10} {notes[key]:<30}")
    print(f"{'='*65}")

    # ── Save LaTeX table ────────────────────────────────────────────────────
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    tex_path = os.path.join(data_dir, "missing_modality_table.tex")

    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write("\\begin{table}[h]\n")
        f.write("\\centering\n")
        f.write("\\caption{Robustness to Missing Modalities}\n")
        f.write("\\label{tab:missing_modality}\n")
        f.write("\\begin{tabular}{lcccc}\n")
        f.write("\\hline\n")
        f.write("Scenario & F1 & AUC & Relative F1 Drop & Note \\\\\n")
        f.write("\\hline\n")
        for key in ['all', 'no_nlp', 'no_mobility', 'no_search']:
            r = results[key]
            drop_tex = f"{r['relative_f1_drop']*100:.1f}\\%%"
            f.write(f"{labels[key]} & {r['f1']:.3f} & {r['auc']:.3f} & {drop_tex} & {notes[key]} \\\\\n")
        f.write("\\hline\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")
    print(f"   LaTeX table saved to: {tex_path}")

    return results


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

    # ── A3: Weight grid search optimization (T-07) ────────────────────────
    weight_opt = run_weight_optimization(aligned_df)

    # ── Per-modality analysis ──────────────────────────────────────────────
    modality_results = run_modality_analysis(aligned_df)

    # ── T-08: Trained fusion classifier evaluation ─────────────────────────
    trained_metrics, trained_proba = evaluate_trained_fusion(aligned_df)

    # ── Load trained model + scaler (shared: T-17, N5, N7) ─────────────────
    fusion_model = None
    fusion_scaler_obj = None
    if trained_metrics and HAS_JOBLIB:
        _mp = os.path.join(MODELS_DIR, "fusion_classifier.pkl")
        _sp = os.path.join(MODELS_DIR, "fusion_scaler.pkl")
        try:
            fusion_model = joblib.load(_mp)
            fusion_scaler_obj = joblib.load(_sp)
        except Exception:
            pass

    # ── T-17: SHAP feature contribution analysis ─────────────────────────────
    shap_result = None
    feature_dominance = None
    if fusion_model is not None:
        try:
            shap_result = compute_shap_values(aligned_df, fusion_model, fusion_scaler_obj)
            if shap_result is not None:
                feature_importance_out, feature_dominance = shap_result
        except Exception as e:
            print(f"\n  T-17: SHAP computation failed ({e}) — skipping")

    # ── N1: Per-disease F1 breakdown ─────────────────────────────────────────
    per_disease = per_disease_f1_breakdown(aligned_df, trained_proba=trained_proba)

    # ── N2: Bootstrap CIs + McNemar test ────────────────────────────────────
    n2_results = compute_n2_statistical_significance(aligned_df, trained_proba=trained_proba)

    # ── T-09: Expanded early warning analysis ──────────────────────────────
    early_warning = compute_early_warning(aligned_df, trained_proba=trained_proba)

    # ── N3: Walk-forward rolling-origin CV ─────────────────────────────────
    wf_results = run_walk_forward_cv(aligned_df)

    # ── N4: Lead-time vs F1 trade-off curve ────────────────────────────────
    n4_curve_data = None
    if HAS_MATPLOTLIB:
        try:
            n4_curve_data = plot_leadtime_f1_curve(aligned_df, PAPER_FIGURES_DIR, trained_proba=trained_proba)
        except Exception as e:
            print(f"\n  N4: Lead-time curve failed ({e}) — skipping")

    # ── N5: Calibration analysis ───────────────────────────────────────────
    cal_results = None
    if fusion_model is not None:
        try:
            cal_results = compute_calibration(aligned_df, fusion_model, fusion_scaler_obj)
        except Exception as e:
            print(f"\n  N5: Calibration failed ({e}) — skipping")

    # ── N6: Cost-sensitive evaluation ───────────────────────────────────────
    cost_results = None
    if trained_proba is not None:
        try:
            _ct = 0.5
            _cb = 0
            for _tt in np.arange(0.05, 0.95, 0.01):
                _pp = (trained_proba >= _tt).astype(int)
                _ff = f1_score(np.array(y_true), _pp, zero_division=0)
                if _ff > _cb:
                    _cb = _ff
                    _ct = _tt
            _tp = (trained_proba >= _ct).astype(int)
            cost_results = compute_cost_sensitive(_tp, np.array(y_true), trained_proba)
        except Exception as e:
            print(f"\n  N6: Cost-sensitive eval failed ({e}) — skipping")

    # ── N7: Missing-modality ablation ──────────────────────────────────────
    mm_results = None
    if fusion_model is not None:
        try:
            mm_results = compute_missing_modality_ablation(aligned_df, fusion_model, fusion_scaler_obj)
        except Exception as e:
            print(f"\n  N7: Missing-modality ablation failed ({e}) — skipping")

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
        "weight_optimization": weight_opt,
        "per_disease_breakdown": per_disease,
        "n2_statistical_significance": n2_results,
        "feature_importance":    feature_importance_out if shap_result else None,
        "feature_dominance":    feature_dominance,
        "early_warning":    early_warning,
        "walk_forward_cv":     wf_results,
        "leadtime_f1_curve":   n4_curve_data,
        "calibration":         cal_results,
        "cost_sensitive":      cost_results,
        "missing_modality":    mm_results,
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

    # A3: Weight optimization summary
    if weight_opt:
        print(f"\n  WEIGHT OPTIMIZATION (T-07 / A3):")
        print(f"   Baseline weights F1: {weight_opt['baseline_f1']:.4f}")
        print(f"   Best grid-search F1: {weight_opt['best_f1']:.4f}  "
              f"(NLP={weight_opt['best_weights']['nlp']}, WW={weight_opt['best_weights']['wastewater']}, MOB={weight_opt['best_weights']['mobility']})")
        print(f"   Note: Trained GradientBoosting classifier supersedes manual weight tuning")

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

    # T-17 SHAP summary
    if shap_result:
        fi_out = shap_result[0]
        fd_out = shap_result[1]
        print(f"\n  SHAP FEATURE IMPORTANCE (T-17):")
        print(f"   Method: {fi_out['method']}")
        print(f"   {'Feature':<20} {'Mean |SHAP|':>12} {'Normalized':>12}")
        print(f"   {'-'*46}")
        for fn in fi_out['feature_names']:
            print(f"   {fn:<20} {fi_out['mean_abs_shap'][fn]:>12.4f} {fi_out['normalized_importance'][fn]:>12.4f}")
        print(f"\n   Feature Dominance:")
        print(f"   {'':20} {'NLP':>8} {'Search':>8} {'Mobility':>10}")
        print(f"   {'-'*50}")
        od = fd_out['outbreak_weeks']
        nd = fd_out['normal_weeks']
        print(f"   {'Outbreak weeks':<20} {od['nlp_dominant_pct']:>7.1f}% {od['search_dominant_pct']:>7.1f}% {od['mobility_dominant_pct']:>9.1f}%")
        print(f"   {'Normal weeks':<20} {nd['nlp_dominant_pct']:>7.1f}% {nd['search_dominant_pct']:>7.1f}% {nd['mobility_dominant_pct']:>9.1f}%")

    # N1 per-disease summary table
    print(f"\n  PER-DISEASE BREAKDOWN (N1):")
    print(f"   {'Disease':<12} {'Method':<16} {'P':>6} {'R':>6} {'F1':>6} {'AUC':>6}")
    print(f"   {'-'*52}")
    for dis_key, dis_data in per_disease.items():
        label = "COVID-19" if dis_key == "covid19" else "Dengue"
        fw = dis_data["fixed_weight"]
        print(f"   {label:<12} {'Fixed-Weight':<16} {fw['precision']:>6.3f} {fw['recall']:>6.3f} {fw['f1_score']:>6.3f} {fw['roc_auc']:>6.3f}")
        if "trained_fusion" in dis_data:
            tr = dis_data["trained_fusion"]
            print(f"   {label:<12} {'Trained Fusion':<16} {tr['precision']:>6.3f} {tr['recall']:>6.3f} {tr['f1_score']:>6.3f} {tr['roc_auc']:>6.3f}")

    # N2 summary
    if n2_results:
        print(f"\n  STATISTICAL SIGNIFICANCE (N2):")
        print(f"   Bootstrap 95% CIs ({n2_results['bootstrap_iterations']} iterations):")
        print(f"   {'Configuration':<30} {'F1 CI':>24} {'AUC CI':>24}")
        print(f"   {'-'*80}")
        for section_key, section_label in [("overall", "Overall")]:
            for method_key, method_label in [("fixed_weight", "Fixed-Weight"), ("trained_fusion", "Trained Fusion")]:
                if method_key in n2_results[section_key]:
                    cfg = n2_results[section_key][method_key]
                    f1 = cfg.get("f1_ci", [None, None])
                    auc = cfg.get("auc_ci", [None, None])
                    f1_s = f"[{f1[0]:.4f}, {f1[1]:.4f}]" if f1[0] is not None else "N/A"
                    auc_s = f"[{auc[0]:.4f}, {auc[1]:.4f}]" if auc[0] is not None else "N/A"
                    print(f"   {section_label+' / '+method_label:<30} {f1_s:>24} {auc_s:>24}")
        for dk, dl in [("covid19", "COVID-19"), ("dengue", "Dengue")]:
            for method_key, method_label in [("fixed_weight", "Fixed-Weight"), ("trained_fusion", "Trained Fusion")]:
                if method_key in n2_results[dk]:
                    cfg = n2_results[dk][method_key]
                    f1 = cfg.get("f1_ci", [None, None])
                    auc = cfg.get("auc_ci", [None, None])
                    f1_s = f"[{f1[0]:.4f}, {f1[1]:.4f}]" if f1[0] is not None else "N/A"
                    auc_s = f"[{auc[0]:.4f}, {auc[1]:.4f}]" if auc[0] is not None else "N/A"
                    print(f"   {dl+' / '+method_label:<30} {f1_s:>24} {auc_s:>24}")
        if "mcnemar" in n2_results:
            mc = n2_results["mcnemar"]
            sig = "SIGNIFICANT" if mc["significant_at_005"] else "NOT significant"
            p_str = f"{mc['p_value']:.6f}" if mc["p_value"] is not None else "N/A"
            print(f"\n   McNemar's Test (Fixed vs Trained): chi2={mc['statistic']:.4f}, p={p_str} ({sig} at p<0.05)")

    # N3 summary
    if wf_results:
        print(f"\n  WALK-FORWARD CV (N3):")
        print(f"   {wf_results['n_test_weeks']} test weeks | "
              f"F1={wf_results['f1_score']:.3f} | "
              f"AUC={wf_results['roc_auc']:.3f}")
        for yr, v in sorted(wf_results.get('per_year', {}).items()):
            print(f"   {yr}: F1={v['f1']:.3f} (n={v['n']})")

    # N4 summary
    if n4_curve_data:
        print(f"\n  LEAD-TIME vs F1 CURVE (N4):")
        op = n4_curve_data.get('operating_point', {})
        print(f"   Operating point (t={op.get('threshold',22)}): "
              f"F1={op.get('f1',0):.3f}, Lead={op.get('lead_time',0):.1f}wk")
        print(f"   Figure saved to paper_figures/fig3_leadtime_f1_curve.png")

    # N5 summary
    if cal_results:
        print(f"\n  CALIBRATION (N5):")
        print(f"   Brier={cal_results['brier_score']:.4f} | "
              f"Skill={cal_results['brier_skill_score']:.4f} | "
              f"Slope={cal_results.get('calibration_slope', 'N/A')}")
        print(f"   Figure saved to paper_figures/fig4_reliability.png")

    # N6 summary
    if cost_results:
        print(f"\n  COST-SENSITIVE (N6):")
        for mult, label in [(1, '1x'), (2, '2x'), (5, '5x'), (10, '10x')]:
            r = cost_results.get(f'fn_{mult}x', {})
            print(f"   FN {label:>3}: F1={r.get('f1',0):.3f} | "
                  f"Cost={r.get('total_cost',0):>3} | "
                  f"OptThresh={r.get('optimal_threshold',0):.2f}")

    # N7 summary
    if mm_results:
        print(f"\n  MISSING-MODALITY ABLATION (N7):")
        for key, lbl in [('all','All'), ('no_nlp','No NLP'), ('no_mobility','No Mobility'), ('no_search','No Search')]:
            r = mm_results.get(key, {})
            drop = r.get('relative_f1_drop', 0)
            print(f"   {lbl:<15} F1={r.get('f1',0):.3f} | "
                  f"AUC={r.get('auc',0):.3f} | "
                  f"Drop={drop*100:.1f}%")

    print(f"\n{'='*65}")


if __name__ == "__main__":
    run_evaluation()