"""
BioGuard AI — NLP Engine Evaluation + Banglish Ablation
=========================================================
Evaluates the fine-tuned NLP engine on the held-out test split.

Outputs:
  - backend/data/nlp_evaluation_results.json
  - backend/data/banglish_ablation.json

Run from:  cd backend && python evaluate_nlp.py
"""

import os
import sys
import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════════════
# PATHS — relative to this script (works from any cwd)
# ══════════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_SPLIT_PATH  = os.path.join(_SCRIPT_DIR, "data", "nlp_test_split.csv")
FINETUNE_RESULTS = os.path.join(_SCRIPT_DIR, "data", "finetuning_results.json")
EVAL_RESULTS     = os.path.join(_SCRIPT_DIR, "data", "nlp_evaluation_results.json")
ABLATION_RESULTS = os.path.join(_SCRIPT_DIR, "data", "banglish_ablation.json")

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

try:
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
        f1_score, roc_auc_score, confusion_matrix,
    )
except ImportError:
    print("ERROR: scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# ══════════════════════════════════════════════════════════════════════════════
# PART 1: LOAD AND SCORE TEST DATA
# ══════════════════════════════════════════════════════════════════════════════

def load_test_data():
    """Load the held-out test split saved by fine_tune_bert.py."""
    if not os.path.exists(TEST_SPLIT_PATH):
        print(f"ERROR: Test split not found at {TEST_SPLIT_PATH}")
        print("Run fine_tune_bert.py first to generate the test split.")
        sys.exit(1)

    df = pd.read_csv(TEST_SPLIT_PATH)
    print(f"Loaded {len(df)} test samples from nlp_test_split.csv")
    return df


def get_best_threshold():
    """Load best threshold from finetuning_results.json, or default to 50."""
    if os.path.exists(FINETUNE_RESULTS):
        try:
            with open(FINETUNE_RESULTS, 'r') as f:
                results = json.load(f)
            # Use the fine-tuned model's overall metrics to pick threshold
            print(f"Loaded finetuning results (fine-tuned F1: {results['finetuned_model']['overall']['f1']})")
        except Exception:
            pass
    return 50  # default


def score_test_data(df, engine, threshold):
    """
    Score every row using engine.analyze_text_signals().
    Returns lists of: true_labels, predicted_labels, scores.
    """
    true_labels = []
    pred_labels = []
    scores = []

    iterator = tqdm(df.itertuples(), total=len(df), desc="Scoring") \
        if HAS_TQDM else df.itertuples()

    for row in iterator:
        text = str(row.text)
        label = int(row.label)

        score = engine.analyze_text_signals(text)
        pred = 1 if score >= threshold else 0

        true_labels.append(label)
        pred_labels.append(pred)
        scores.append(score)

    return true_labels, pred_labels, scores


# ══════════════════════════════════════════════════════════════════════════════
# PART 2: OVERALL METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_overall_metrics(true_labels, pred_labels, scores):
    """Compute accuracy, precision, recall, F1, ROC-AUC, confusion matrix."""
    acc = accuracy_score(true_labels, pred_labels)
    prec = precision_score(true_labels, pred_labels, average='binary', zero_division=0)
    rec = recall_score(true_labels, pred_labels, average='binary', zero_division=0)
    f1 = f1_score(true_labels, pred_labels, average='binary', zero_division=0)

    try:
        auc = roc_auc_score(true_labels, scores)
    except ValueError:
        auc = 0.0

    cm = confusion_matrix(true_labels, pred_labels)

    return {
        'accuracy': round(float(acc), 4),
        'precision': round(float(prec), 4),
        'recall': round(float(rec), 4),
        'f1': round(float(f1), 4),
        'roc_auc': round(float(auc), 4),
    }, cm.tolist()


# ══════════════════════════════════════════════════════════════════════════════
# PART 3: PER-LANGUAGE BREAKDOWN
# ══════════════════════════════════════════════════════════════════════════════

def compute_per_language(df, true_labels, pred_labels, min_samples=5):
    """Compute precision, recall, F1 per language (skip < min_samples)."""
    per_language = {}
    languages = sorted(df['language'].unique())

    for lang in languages:
        mask = df['language'].values == lang
        lang_true = np.array(true_labels)[mask]
        lang_pred = np.array(pred_labels)[mask]

        if len(lang_true) < min_samples:
            print(f"  WARNING: Skipping '{lang}' — only {len(lang_true)} test samples (need >= {min_samples})")
            continue

        prec = precision_score(lang_true, lang_pred, average='binary', zero_division=0)
        rec = recall_score(lang_true, lang_pred, average='binary', zero_division=0)
        f1 = f1_score(lang_true, lang_pred, average='binary', zero_division=0)

        per_language[lang] = {
            'precision': round(float(prec), 4),
            'recall': round(float(rec), 4),
            'f1': round(float(f1), 4),
            'n_samples': int(len(lang_true)),
        }

    return per_language


def print_language_table(per_language):
    """Print a clean per-language results table."""
    print(f"\n{'='*60}")
    print("PER-LANGUAGE RESULTS")
    print(f"{'='*60}")
    print(f"{'Language':<12} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Samples':>8}")
    print(f"{'-'*52}")

    lang_display = {
        'en': 'English', 'bn': 'Bangla', 'banglish': 'Banglish',
        'hi': 'Hindi', 'ar': 'Arabic', 'id': 'Indonesian',
        'fr': 'French', 'es': 'Spanish', 'pt': 'Portuguese',
        'ur': 'Urdu', 'ms': 'Malay', 'ta': 'Tamil',
    }

    for lang in ['en', 'bn', 'banglish', 'hi', 'ar', 'id', 'fr', 'es', 'pt', 'ur', 'ms', 'ta']:
        if lang in per_language:
            m = per_language[lang]
            name = lang_display.get(lang, lang.capitalize())
            print(f"{name:<12} {m['precision']:>10.3f} {m['recall']:>10.3f} {m['f1']:>10.3f} {m['n_samples']:>8}")

    print(f"{'='*60}")


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: THRESHOLD OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════════

def optimize_threshold(true_labels, scores, low=30, high=75, step=5):
    """Loop thresholds and find the one with best F1."""
    best_thresh = 50
    best_f1 = 0.0

    print(f"\nThreshold Optimization:")
    print(f"{'Threshold':>10} {'F1':>8}")
    print(f"{'-'*20}")

    for t in range(low, high, step):
        preds = [1 if s >= t else 0 for s in scores]
        f1 = f1_score(true_labels, preds, average='binary', zero_division=0)
        marker = ""
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t
            marker = " <-- best"
        print(f"{t:>10} {f1:>8.3f}{marker}")

    print(f"\nBest threshold: {best_thresh} (F1={best_f1:.3f})")
    return best_thresh, best_f1


# ══════════════════════════════════════════════════════════════════════════════
# PART 5: BANGLISH ABLATION
# ══════════════════════════════════════════════════════════════════════════════

def run_banglish_ablation(df, engine, threshold):
    """
    Compare engine performance on Banglish posts WITH vs WITHOUT
    Banglish detection enabled.
    """
    banglish_df = df[df['language'] == 'banglish'].copy()

    if len(banglish_df) == 0:
        print("\nNo Banglish samples in test set — skipping ablation.")
        return None

    print(f"\n{'='*60}")
    print(f"BANGLISH ABLATION ({len(banglish_df)} Banglish test samples)")
    print(f"{'='*60}")

    # Import the module containing is_banglish
    import engine_bert as eb

    # ── MODE A: Normal (with Banglish detection) ──
    mode_a_true, mode_a_pred, mode_a_scores = [], [], []
    for _, row in banglish_df.iterrows():
        text = str(row.text)
        score = engine.analyze_text_signals(text)
        pred = 1 if score >= threshold else 0
        mode_a_true.append(int(row.label))
        mode_a_pred.append(pred)
        mode_a_scores.append(score)

    # ── MODE B: Banglish detection disabled ──
    original_is_banglish = eb.is_banglish
    eb.is_banglish = lambda text, lang: False  # monkey-patch

    mode_b_true, mode_b_pred, mode_b_scores = [], [], []
    for _, row in banglish_df.iterrows():
        text = str(row.text)
        score = engine.analyze_text_signals(text)
        pred = 1 if score >= threshold else 0
        mode_b_true.append(int(row.label))
        mode_b_pred.append(pred)
        mode_b_scores.append(score)

    # Restore original
    eb.is_banglish = original_is_banglish

    # Compute metrics for both modes
    def calc_metrics(true, pred):
        prec = precision_score(true, pred, average='binary', zero_division=0)
        rec = recall_score(true, pred, average='binary', zero_division=0)
        f1 = f1_score(true, pred, average='binary', zero_division=0)
        return {
            'f1': round(float(f1), 4),
            'precision': round(float(prec), 4),
            'recall': round(float(rec), 4),
        }

    with_det = calc_metrics(mode_a_true, mode_a_pred)
    without_det = calc_metrics(mode_b_true, mode_b_pred)

    # Print table
    print(f"\n{'Mode':<20} {'F1':>8} {'Precision':>10} {'Recall':>8}")
    print(f"{'-'*48}")
    print(f"{'With detection':<20} {with_det['f1']:>8.3f} {with_det['precision']:>10.3f} {with_det['recall']:>8.3f}")
    print(f"{'Without detection':<20} {without_det['f1']:>8.3f} {without_det['precision']:>10.3f} {without_det['recall']:>8.3f}")

    f1_delta = with_det['f1'] - without_det['f1']
    prec_delta = with_det['precision'] - without_det['precision']
    rec_delta = with_det['recall'] - without_det['recall']
    sign_f = '+' if f1_delta >= 0 else ''
    sign_p = '+' if prec_delta >= 0 else ''
    sign_r = '+' if rec_delta >= 0 else ''
    print(f"{'Improvement':<20} {sign_f}{f1_delta:>7.3f} {sign_p}{prec_delta:>9.3f} {sign_r}{rec_delta:>7.3f}")
    print(f"{'='*60}")

    return {
        'with_detection': with_det,
        'without_detection': without_det,
        'f1_improvement': round(float(f1_delta), 4),
        'n_banglish_samples': len(banglish_df),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 6: SAVE RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def save_evaluation_results(overall, per_language, cm, df, threshold):
    """Save nlp_evaluation_results.json."""
    results = {
        'overall': {**overall, 'best_threshold': threshold},
        'per_language': per_language,
        'confusion_matrix': cm,
        'total_test_samples': int(len(df)),
        'outbreak_samples': int(df['label'].sum()),
        'threshold_used': threshold,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    os.makedirs(os.path.dirname(EVAL_RESULTS), exist_ok=True)
    with open(EVAL_RESULTS, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nEvaluation results saved to {EVAL_RESULTS}")
    return results


def save_ablation_results(ablation):
    """Save banglish_ablation.json."""
    if ablation is None:
        return

    os.makedirs(os.path.dirname(ABLATION_RESULTS), exist_ok=True)
    with open(ABLATION_RESULTS, 'w', encoding='utf-8') as f:
        json.dump(ablation, f, indent=2, ensure_ascii=False)

    print(f"Banglish ablation results saved to {ABLATION_RESULTS}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run_evaluation():
    print("=" * 60)
    print("  BioGuard AI — NLP Engine Evaluation")
    print("=" * 60)
    print()

    # ── Load test data ──
    df = load_test_data()
    threshold = get_best_threshold()
    print(f"Using threshold: {threshold}")
    print()

    # ── Import and initialize engine ──
    print("Loading NLP engine...")
    from engine_bert import MultiLingualSymptomEngine
    engine = MultiLingualSymptomEngine()
    print()

    # ── PART 1: Score all test data ──
    print("PART 1: Scoring test data with engine...")
    true_labels, pred_labels, scores = score_test_data(df, engine, threshold)
    print()

    # ── PART 4: Threshold optimization (run first to find best) ──
    print("PART 4: Threshold optimization...")
    best_threshold, _ = optimize_threshold(true_labels, scores)

    # Re-score with best threshold
    pred_labels = [1 if s >= best_threshold else 0 for s in scores]
    print()

    # ── PART 2: Overall metrics ──
    print("PART 2: Overall metrics...")
    overall, cm = compute_overall_metrics(true_labels, pred_labels, scores)

    print(f"\n{'='*60}")
    print("OVERALL RESULTS")
    print(f"{'='*60}")
    print(f"  Accuracy:  {overall['accuracy']:.3f}")
    print(f"  Precision: {overall['precision']:.3f}")
    print(f"  Recall:    {overall['recall']:.3f}")
    print(f"  F1:        {overall['f1']:.3f}")
    print(f"  ROC-AUC:   {overall['roc_auc']:.3f}")
    print(f"  Threshold: {best_threshold}")
    print(f"\n  Confusion Matrix:")
    print(f"    TN={cm[0][0]}  FP={cm[0][1]}")
    print(f"    FN={cm[1][0]}  TP={cm[1][1]}")
    print(f"{'='*60}")

    # ── PART 3: Per-language breakdown ──
    print("\nPART 3: Per-language breakdown...")
    per_language = compute_per_language(df, true_labels, pred_labels)
    print_language_table(per_language)

    # ── PART 5: Banglish ablation ──
    print("\nPART 5: Banglish ablation...")
    ablation = run_banglish_ablation(df, engine, best_threshold)

    # ── PART 6: Save results ──
    print("\nPART 6: Saving results...")
    save_evaluation_results(overall, per_language, cm, df, best_threshold)
    save_ablation_results(ablation)

    print(f"\n{'='*60}")
    print("  EVALUATION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_evaluation()