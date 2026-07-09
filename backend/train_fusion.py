"""
BioGuard AI — Fusion Classifier Training (A-NEW-2)
===================================================
Trains three fusion classifiers (Logistic Regression, Random Forest,
Gradient Boosting) on the 156-week ground truth using the three signal
scores as features and outbreak_label as target.

Uses 5-fold stratified cross-validation. Picks best model by F1,
retrains on all 156 weeks, saves to backend/models/fusion_classifier.pkl.

Run:  cd backend && python train_fusion.py
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

warnings.filterwarnings('ignore')

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── sklearn imports ───────────────────────────────────────────────────────────
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.preprocessing import MinMaxScaler

try:
    import joblib
except ImportError:
    print("joblib not found. Installing via scikit-learn...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "joblib"])
    import joblib

# ── constants ─────────────────────────────────────────────────────────────────
N_FOLDS       = 5
RANDOM_STATE  = 42
THRESHOLD     = 22.0
FEATURE_COLS  = ['nlp_proxy', 'wastewater_proxy', 'mobility_score']
TARGET_COL    = 'outbreak_label'

DATA_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODEL_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH     = os.path.join(MODEL_DIR, "fusion_classifier.pkl")
SCALER_PATH    = os.path.join(MODEL_DIR, "fusion_scaler.pkl")
OUTPUT_JSON    = os.path.join(DATA_DIR, "fusion_training_results.json")

# Fixed baseline weights (from app.py / evaluate.py)
BASELINE_WEIGHTS = {"nlp": 0.25, "wastewater": 0.40, "mobility": 0.35}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load and align data (reuse from evaluate.py)
# ══════════════════════════════════════════════════════════════════════════════

def load_aligned_data():
    """Load ground truth + signals using evaluate.py functions."""
    from evaluate import (
        load_ground_truth, load_trends_series,
        load_mobility_series, load_iedcr_series,
        build_weekly_signals
    )

    print("=" * 65)
    print("A-NEW-2: Fusion Classifier Training")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    gt_df       = load_ground_truth()
    trends_df   = load_trends_series(zone_id=11)
    mobility_df = load_mobility_series(zone_id=11)
    iedcr_df    = load_iedcr_series()

    aligned_df = build_weekly_signals(gt_df, trends_df, mobility_df, iedcr_df)

    if aligned_df.empty:
        print("\nERROR: No aligned data produced. Check CSV files and MongoDB.")
        sys.exit(1)

    if len(aligned_df) < 50:
        print(f"\nERROR: Only {len(aligned_df)} rows. Need at least 50.")
        sys.exit(1)

    return aligned_df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Compute baseline (fixed-weight) CV metrics
# ══════════════════════════════════════════════════════════════════════════════

def compute_baseline_cv(X, y, scaler, cv):
    """Compute 5-fold CV metrics for the fixed-weight baseline."""
    print("\nComputing baseline (fixed-weight) CV metrics...")

    fold_f1s = []
    fold_aucs = []

    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Scale
        scaler_fold = MinMaxScaler()
        X_train_s = scaler_fold.fit_transform(X_train)
        X_test_s  = scaler_fold.transform(X_test)

        # Fixed-weight fused score (on raw unscaled values for fair comparison)
        fixed_train = (X_train[:, 0] * BASELINE_WEIGHTS['nlp'] +
                       X_train[:, 1] * BASELINE_WEIGHTS['wastewater'] +
                       X_train[:, 2] * BASELINE_WEIGHTS['mobility'])
        fixed_test  = (X_test[:, 0] * BASELINE_WEIGHTS['nlp'] +
                       X_test[:, 1] * BASELINE_WEIGHTS['wastewater'] +
                       X_test[:, 2] * BASELINE_WEIGHTS['mobility'])

        # Find optimal threshold on train set
        best_f1 = 0
        best_t = THRESHOLD / 100.0  # normalize to 0-1 scale roughly
        for t in np.arange(0.05, 0.95, 0.05):
            preds = (fixed_train >= t).astype(int)
            f1 = f1_score(y_train, preds, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_t = t

        # Apply to test
        test_preds = (fixed_test >= best_t).astype(int)
        fold_f1s.append(f1_score(y_test, test_preds, zero_division=0))
        try:
            fold_aucs.append(roc_auc_score(y_test, fixed_test))
        except Exception:
            fold_aucs.append(0.0)

    return {
        "cv_f1_mean": round(float(np.mean(fold_f1s)), 4),
        "cv_f1_std":  round(float(np.std(fold_f1s)), 4),
        "cv_auc_mean": round(float(np.mean(fold_aucs)), 4),
        "cv_auc_std":  round(float(np.std(fold_aucs)), 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Train and cross-validate all three classifiers
# ══════════════════════════════════════════════════════════════════════════════

def train_and_evaluate(X_scaled, y, cv):
    """Train 3 classifiers with 5-fold CV, return all results."""
    print("\nTraining classifiers with 5-fold Stratified Cross-Validation...")

    models = {
        "logistic_regression": LogisticRegression(
            C=1.0, max_iter=1000, random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=100, max_depth=4, random_state=RANDOM_STATE
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=100, max_depth=2, learning_rate=0.1,
            random_state=RANDOM_STATE
        ),
    }

    scoring = ['f1', 'precision', 'recall', 'roc_auc']
    results = {}

    for name, model in models.items():
        print(f"   Training {name}...")
        cv_results = cross_validate(
            model, X_scaled, y,
            cv=cv, scoring=scoring, return_estimator=True
        )

        r = {
            "cv_f1_mean":       round(float(cv_results['test_f1'].mean()), 4),
            "cv_f1_std":        round(float(cv_results['test_f1'].std()), 4),
            "cv_auc_mean":      round(float(cv_results['test_roc_auc'].mean()), 4),
            "cv_auc_std":       round(float(cv_results['test_roc_auc'].std()), 4),
            "cv_precision_mean": round(float(cv_results['test_precision'].mean()), 4),
            "cv_recall_mean":   round(float(cv_results['test_recall'].mean()), 4),
        }

        # Extract learned weights/feature importances
        best_fold_idx = cv_results['test_f1'].argmax()
        best_est = cv_results['estimator'][best_fold_idx]

        if name == "logistic_regression":
            coefs = best_est.coef_[0]
            abs_coefs = np.abs(coefs)
            total = abs_coefs.sum()
            r["coefficients"] = {
                "nlp":        round(float(abs_coefs[0] / total), 4),
                "wastewater": round(float(abs_coefs[1] / total), 4),
                "mobility":   round(float(abs_coefs[2] / total), 4),
            }
        else:
            imps = best_est.feature_importances_
            r["feature_importances"] = {
                "nlp":        round(float(imps[0]), 4),
                "wastewater": round(float(imps[1]), 4),
                "mobility":   round(float(imps[2]), 4),
            }

        results[name] = r

    return results, models


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Load data ────────────────────────────────────────────────────────
    aligned_df = load_aligned_data()

    X = aligned_df[FEATURE_COLS].values
    y = aligned_df[TARGET_COL].values

    outbreak_count = int(y.sum())
    normal_count   = int(len(y) - y.sum())

    print(f"\n   Training data: {len(X)} samples x {X.shape[1]} features")
    print(f"   Class balance: {outbreak_count} outbreak weeks ({outbreak_count/len(y)*100:.1f}%), "
          f"{normal_count} normal weeks ({normal_count/len(y)*100:.1f}%)")

    # ── Normalize features ───────────────────────────────────────────────
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"\n   Features normalized with MinMaxScaler")

    # ── Cross-validation setup ──────────────────────────────────────────
    cv = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    # ── Baseline ─────────────────────────────────────────────────────────
    baseline = compute_baseline_cv(X, y, scaler, cv)

    # ── Train classifiers ───────────────────────────────────────────────
    clf_results, models = train_and_evaluate(X_scaled, y, cv)

    # ── Pick best model ─────────────────────────────────────────────────
    best_name = max(clf_results, key=lambda k: clf_results[k]['cv_f1_mean'])
    best_f1   = clf_results[best_name]['cv_f1_mean']
    best_auc  = clf_results[best_name]['cv_auc_mean']
    base_f1   = baseline['cv_f1_mean']
    base_auc  = baseline['cv_auc_mean']

    print(f"\n{'='*65}")
    print("FUSION MODEL COMPARISON (5-fold Stratified Cross-Validation)")
    print(f"{'='*65}")
    print(f"   {'Model':<30} {'Mean F1':>10} {'SD':>8} {'Mean AUC':>10} {'SD':>8}")
    print(f"   {'-'*70}")
    print(f"   {'Fixed Weights (baseline)':<30} {baseline['cv_f1_mean']:>10.4f} "
          f"{baseline['cv_f1_std']:>8.4f} {baseline['cv_auc_mean']:>10.4f} "
          f"{baseline['cv_auc_std']:>8.4f}")

    for name, r in clf_results.items():
        label = name.replace('_', ' ').title()
        print(f"   {label:<30} {r['cv_f1_mean']:>10.4f} "
              f"{r['cv_f1_std']:>8.4f} {r['cv_auc_mean']:>10.4f} "
              f"{r['cv_auc_std']:>8.4f}")

    print(f"{'='*65}")
    f1_improvement = round(best_f1 - base_f1, 4)
    auc_improvement = round(best_auc - base_auc, 4)
    print(f"   Best model: {best_name} | F1 improvement over baseline: +{f1_improvement}")
    print(f"{'='*65}")

    # ── Retrain best model on ALL data ───────────────────────────────────
    print(f"\nRetraining {best_name} on all {len(X)} samples...")
    best_model = models[best_name]
    best_model.fit(X_scaled, y)

    # ── Save model and scaler ───────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"   Model saved to: {MODEL_PATH}")
    print(f"   Scaler saved to: {SCALER_PATH}")

    # ── Print learned weights ───────────────────────────────────────────
    if best_name == "logistic_regression":
        coefs = np.abs(best_model.coef_[0])
        total = coefs.sum()
        learned = {
            "nlp":        round(float(coefs[0] / total), 4),
            "wastewater": round(float(coefs[1] / total), 4),
            "mobility":   round(float(coefs[2] / total), 4),
        }
        weight_label = "coefficients"
    else:
        imps = best_model.feature_importances_
        learned = {
            "nlp":        round(float(imps[0]), 4),
            "wastewater": round(float(imps[1]), 4),
            "mobility":   round(float(imps[2]), 4),
        }
        weight_label = "feature_importances"

    print(f"\n   LEARNED SIGNAL WEIGHTS ({weight_label}):")
    print(f"     nlp_proxy:        {learned['nlp']:.4f}  (was fixed: {BASELINE_WEIGHTS['nlp']})")
    print(f"     wastewater_proxy: {learned['wastewater']:.4f}  (was fixed: {BASELINE_WEIGHTS['wastewater']})")
    print(f"     mobility_score:   {learned['mobility']:.4f}  (was fixed: {BASELINE_WEIGHTS['mobility']})")

    # ── Build output JSON ───────────────────────────────────────────────
    output = {
        "baseline_fixed_weights": {
            "weights": BASELINE_WEIGHTS,
            "threshold": THRESHOLD,
            "cv_f1_mean": baseline['cv_f1_mean'],
            "cv_f1_std":  baseline['cv_f1_std'],
            "cv_auc_mean": baseline['cv_auc_mean'],
            "cv_auc_std":  baseline['cv_auc_std'],
        },
        "logistic_regression": {
            "cv_f1_mean":        clf_results["logistic_regression"]["cv_f1_mean"],
            "cv_f1_std":         clf_results["logistic_regression"]["cv_f1_std"],
            "cv_auc_mean":       clf_results["logistic_regression"]["cv_auc_mean"],
            "cv_auc_std":        clf_results["logistic_regression"]["cv_auc_std"],
            "cv_precision_mean": clf_results["logistic_regression"]["cv_precision_mean"],
            "cv_recall_mean":    clf_results["logistic_regression"]["cv_recall_mean"],
            "coefficients":      clf_results["logistic_regression"]["coefficients"],
        },
        "random_forest": {
            "cv_f1_mean":        clf_results["random_forest"]["cv_f1_mean"],
            "cv_f1_std":         clf_results["random_forest"]["cv_f1_std"],
            "cv_auc_mean":       clf_results["random_forest"]["cv_auc_mean"],
            "cv_auc_std":        clf_results["random_forest"]["cv_auc_std"],
            "cv_precision_mean": clf_results["random_forest"]["cv_precision_mean"],
            "cv_recall_mean":    clf_results["random_forest"]["cv_recall_mean"],
            "feature_importances": clf_results["random_forest"]["feature_importances"],
        },
        "gradient_boosting": {
            "cv_f1_mean":        clf_results["gradient_boosting"]["cv_f1_mean"],
            "cv_f1_std":         clf_results["gradient_boosting"]["cv_f1_std"],
            "cv_auc_mean":       clf_results["gradient_boosting"]["cv_auc_mean"],
            "cv_auc_std":        clf_results["gradient_boosting"]["cv_auc_std"],
            "cv_precision_mean": clf_results["gradient_boosting"]["cv_precision_mean"],
            "cv_recall_mean":    clf_results["gradient_boosting"]["cv_recall_mean"],
            "feature_importances": clf_results["gradient_boosting"]["feature_importances"],
        },
        "best_model": {
            "name":                          best_name,
            "cv_f1_mean":                    best_f1,
            "cv_auc_mean":                   best_auc,
            "f1_improvement_over_baseline":  f1_improvement,
            "auc_improvement_over_baseline": auc_improvement,
            "learned_weights":               learned,
        },
        "training_config": {
            "cv_folds":       N_FOLDS,
            "random_state":   RANDOM_STATE,
            "n_features":     X.shape[1],
            "n_samples":      len(X),
            "scaler":         "MinMaxScaler",
            "scaler_path":    "backend/models/fusion_scaler.pkl",
            "model_path":     "backend/models/fusion_classifier.pkl",
        },
        "generated_at": datetime.now().isoformat(),
    }

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to: {OUTPUT_JSON}")
    print(f"\n{'='*65}")
    print("A-NEW-2 COMPLETE — Fusion classifier ready for T-08")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()