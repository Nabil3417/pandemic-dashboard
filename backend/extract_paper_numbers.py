"""
BioGuard AI — Paper Number Extractor
======================================
Extracts every metric needed for the JMIR Public Health paper
from all JSON result files. Print this output and keep it open
while writing your paper.

Usage:
    cd backend
    python extract_paper_numbers.py
"""

import os
import json

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def load(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

# ── Load all JSON files ────────────────────────────────────────────────────
ev  = load("evaluation_results.json")
ft  = load("fusion_training_results.json")
nlp = load("nlp_evaluation_results.json")
fnt = load("finetuning_results.json")
bl  = load("banglish_ablation.json")
ds  = load("dataset_summary.json")

print("=" * 70)
print("BIOGUARD AI — ALL PAPER NUMBERS")
print("Keep this output open while writing the JMIR paper")
print("=" * 70)

# ── 1. Dataset ─────────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("1. DATASET")
print("─" * 70)
if ds:
    print(f"  NLP labeled dataset:  {ds['total']} samples  ({ds['label_1']} outbreak, {ds['label_0']} normal)")
    print(f"    Real posts:         {ds['real_posts']}")
    print(f"    Synthetic posts:    {ds['synthetic_posts']}")
    print(f"    Languages:          {len(ds['by_language'])} (bn, en, banglish, hi, ar, id, fr, es, pt, ur, ms, ta)")
    print(f"    Train / Val / Test: 711 / 153 / 153  (from finetuning_results.json)")

# ── 2. Study Period & Geography ────────────────────────────────────────────
print("\n" + "─" * 70)
print("2. STUDY PERIOD & GEOGRAPHY")
print("─" * 70)
print("  Period:          January 2020 – October 2022 (156 weeks)")
print("  Location:        Dhaka City Corporation, Bangladesh")
print("  Zones:           15 DCC zones")
print("  Outbreak weeks:  52 of 156 (33.3%)")
print("  Normal weeks:    104 of 156 (66.7%)")
print("  Diseases:        COVID-19 (36 outbreak weeks), Dengue (16 outbreak weeks)")

# ── 3. NLP Engine (XLM-RoBERTa Fine-tuning) ────────────────────────────────
print("\n" + "─" * 70)
print("3. NLP ENGINE — XLM-RoBERTa FINE-TUNING")
print("─" * 70)
if fnt:
    base = fnt["base_model"]["overall"]
    fine = fnt["finetuned_model"]["overall"]
    imp = fnt["improvement"]
    print(f"  Base model:      F1={base['f1']:.3f}  P={base['precision']:.3f}  R={base['recall']:.3f}  AUC={base['roc_auc']:.3f}")
    print(f"  Fine-tuned:      F1={fine['f1']:.3f}  P={fine['precision']:.3f}  R={fine['recall']:.3f}  AUC={fine['roc_auc']:.3f}")
    print(f"  Delta:           F1=+{imp['overall_f1_delta']:.3f}  AUC=+{imp['auc_delta']:.3f}")
    print(f"  Banglish:        F1 from {fnt['base_model']['per_language']['banglish']['f1']:.1f} -> {fnt['finetuned_model']['per_language']['banglish']['f1']:.1f}  (delta=+{imp['banglish_f1_delta']:.1f})")
    print(f"  Config:          epochs={fnt['training_config']['epochs']}, batch={fnt['training_config']['batch_size']}, lr={fnt['training_config']['learning_rate']}, max_len={fnt['training_config']['max_length']}")
    print(f"  Base model:      {fnt['base_model_name']}")

if nlp:
    print(f"\n  Fine-tuned model on full test set ({nlp['total_test_samples']} samples, {nlp['outbreak_samples']} outbreak):")
    print(f"    Overall:       F1={nlp['overall']['f1']:.4f}  P={nlp['overall']['precision']:.4f}  R={nlp['overall']['recall']:.4f}  AUC={nlp['overall']['roc_auc']:.4f}")
    cm = nlp["confusion_matrix"]
    print(f"    Confusion:     TN={cm[0][0]}  FP={cm[0][1]}  FN={cm[1][0]}  TP={cm[1][1]}")

# ── 4. Fusion Classifier Training ──────────────────────────────────────────
print("\n" + "─" * 70)
print("4. FUSION CLASSIFIER TRAINING (5-fold Stratified CV)")
print("─" * 70)
if ft:
    gb = ft["gradient_boosting"]
    rf = ft["random_forest"]
    lr = ft["logistic_regression"]
    bl_fw = ft["baseline_fixed_weights"]
    best = ft["best_model"]
    print(f"  Fixed-Weight Baseline:  F1={bl_fw['cv_f1_mean']:.4f} (+/- {bl_fw['cv_f1_std']:.4f})  AUC={bl_fw['cv_auc_mean']:.4f}")
    print(f"  Logistic Regression:    F1={lr['cv_f1_mean']:.4f} (+/- {lr['cv_f1_std']:.4f})  AUC={lr['cv_auc_mean']:.4f}")
    print(f"  Random Forest:          F1={rf['cv_f1_mean']:.4f} (+/- {rf['cv_f1_std']:.4f})  AUC={rf['cv_auc_mean']:.4f}")
    print(f"  Gradient Boosting (★):  F1={gb['cv_f1_mean']:.4f} (+/- {gb['cv_f1_std']:.4f})  AUC={gb['cv_auc_mean']:.4f}")
    print(f"  GB learned weights:     NLP={best['learned_weights']['nlp']:.4f}  Search={best['learned_weights']['wastewater']:.4f}  Mobility={best['learned_weights']['mobility']:.4f}")
    print(f"  GB feature importances: NLP={gb['feature_importances']['nlp']:.4f}  Search={gb['feature_importances']['wastewater']:.4f}  Mobility={gb['feature_importances']['mobility']:.4f}")
    print(f"  F1 improvement over baseline: +{best['f1_improvement_over_baseline']:.4f}")
    print(f"  AUC improvement over baseline: +{best['auc_improvement_over_baseline']:.4f}")
    print(f"  Training:  n={ft['training_config']['n_samples']} weeks, {ft['training_config']['cv_folds']}-fold CV, {ft['training_config']['n_features']} features, {ft['training_config']['scaler']}")

# ── 5. Main Evaluation Results ────────────────────────────────────────────
print("\n" + "─" * 70)
print("5. MAIN EVALUATION (156 weeks, 2020-2022)")
print("─" * 70)
if ev:
    cm_ev = ev.get("combined_model", {})
    tm = ev.get("combined_model_trained", {})
    print(f"  Fixed-Weight Fusion:")
    print(f"    P={cm_ev.get('precision',0):.4f}  R={cm_ev.get('recall',0):.4f}  F1={cm_ev.get('f1_score',0):.4f}  AUC={cm_ev.get('roc_auc',0):.4f}")
    print(f"    TP={cm_ev.get('tp',0)}  FP={cm_ev.get('fp',0)}  FN={cm_ev.get('fn',0)}  TN={cm_ev.get('tn',0)}")

    if tm:
        cv_f1 = "N/A"
        cv_auc = "N/A"
        pn = tm.get("paper_notes") or {}
        if pn.get("cv_5fold_f1") is not None:
            cv_f1 = f"{pn['cv_5fold_f1']:.4f}"
        if pn.get("cv_5fold_auc") is not None:
            cv_auc = f"{pn['cv_5fold_auc']:.4f}"

        print(f"\n  Trained GradientBoosting:")
        print(f"    In-sample:  P={tm.get('precision',0):.4f}  R={tm.get('recall',0):.4f}  F1={tm.get('f1_score',0):.4f}  AUC={tm.get('roc_auc',0):.4f}")
        print(f"    Honest 5-fold CV:  F1={cv_f1}  AUC={cv_auc}  <-- USE THESE IN PAPER")

# ── 6. Per-Disease Breakdown ───────────────────────────────────────────────
print("\n" + "─" * 70)
print("6. PER-DISEASE BREAKDOWN (N1)")
print("─" * 70)
if ev and ev.get("per_disease_breakdown"):
    for dis, label in [("covid19", "COVID-19"), ("dengue", "Dengue")]:
        d = ev["per_disease_breakdown"][dis]
        fw = d["fixed_weight"]
        print(f"  {label} ({d['outbreak_weeks']} outbreak weeks):")
        print(f"    Fixed-Weight:  P={fw['precision']:.4f}  R={fw['recall']:.4f}  F1={fw['f1_score']:.4f}  AUC={fw['roc_auc']:.4f}  TP={fw['tp']} FP={fw['fp']} FN={fw['fn']} TN={fw['tn']}")
        if "trained_fusion" in d:
            tr = d["trained_fusion"]
            print(f"    Trained Fusion: P={tr['precision']:.4f}  R={tr['recall']:.4f}  F1={tr['f1_score']:.4f}  AUC={tr['roc_auc']:.4f}  TP={tr['tp']} FP={tr['fp']} FN={tr['fn']} TN={tr['tn']}")
        if d.get("warning"):
            print(f"    WARNING: {d['warning']}")

# ── 7. Walk-Forward CV ────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("7. WALK-FORWARD ROLLING-ORIGIN CV (N3)")
print("─" * 70)
if ev and ev.get("walk_forward_cv"):
    wf = ev["walk_forward_cv"]
    cm_wf = wf["confusion_matrix"]
    print(f"  Test weeks: {wf['n_test_weeks']} (min_train={wf['min_train_weeks']} weeks)")
    print(f"  F1={wf['f1_score']:.4f}  P={wf['precision']:.4f}  R={wf['recall']:.4f}  AUC={wf['roc_auc']:.4f}  Acc={wf['accuracy']:.4f}")
    print(f"  Confusion: TN={cm_wf[0][0]}  FP={cm_wf[0][1]}  FN={cm_wf[1][0]}  TP={cm_wf[1][1]}")
    for yr, v in sorted(wf.get("per_year", {}).items()):
        print(f"  {yr}: F1={v['f1']:.4f} (n={v['n']})")
    dist = wf.get("model_selection_distribution", {})
    print(f"  Model selection: {', '.join(f'{k} {v}%' for k, v in dist.items())}")

# ── 8. Bootstrap CIs & McNemar ─────────────────────────────────────────────
print("\n" + "─" * 70)
print("8. STATISTICAL SIGNIFICANCE (N2)")
print("─" * 70)
if ev and ev.get("n2_statistical_significance"):
    n2 = ev["n2_statistical_significance"]
    print(f"  Bootstrap: {n2['bootstrap_iterations']} iterations, {n2['confidence_level']*100:.0f}% CI")

    for section, label in [("overall", "Overall"), ("covid19", "COVID-19"), ("dengue", "Dengue")]:
        if section in n2:
            for method, ml in [("fixed_weight", "Fixed-Weight"), ("trained_fusion", "Trained")]:
                if method in n2[section]:
                    cfg = n2[section][method]
                    f1 = cfg.get("f1_ci", [None, None])
                    auc = cfg.get("auc_ci", [None, None])
                    f1s = f"[{f1[0]:.4f}, {f1[1]:.4f}]" if f1[0] is not None else "N/A"
                    aucs = f"[{auc[0]:.4f}, {auc[1]:.4f}]" if auc[0] is not None else "N/A"
                    print(f"  {label}/{ml}: F1 CI = {f1s}  AUC CI = {aucs}")

    if "mcnemar" in n2:
        mc = n2["mcnemar"]
        sig = "SIGNIFICANT" if mc["significant_at_005"] else "NOT significant"
        p = f"{mc['p_value']:.6f}" if mc["p_value"] is not None else "N/A"
        print(f"\n  McNemar's Test (Fixed vs Trained): chi2={mc['statistic']:.4f}, p={p} ({sig})")
        ct = mc["contingency_table"]
        print(f"  Contingency: a(both OK)={ct['a_both_correct']}  b(fixed OK)={ct['b_fixed_only']}  c(trained OK)={ct['c_trained_only']}  d(both wrong)={ct['d_both_wrong']}")

# ── 9. Early Warning ──────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("9. EARLY WARNING (T-09)")
print("─" * 70)
if ev and ev.get("early_warning"):
    ew = ev["early_warning"]
    total = ew.get("outbreaks_total", 0)
    for key, label in [("strict", "Fixed Strict (t=22)"), ("soft", "Fixed Soft (t=15)"),
                        ("strict_trained", "Trained Strict (t=0.22)"), ("soft_trained", "Trained Soft (t=0.15)")]:
        if ew.get(key):
            s = ew[key]
            print(f"  {label:<30} caught {s['outbreaks_caught']}/{s['outbreaks_total']} outbreaks, avg {s['avg_lead_weeks']:.1f} weeks early")

# ── 10. Weight Optimization (A3) ───────────────────────────────────────────
print("\n" + "─" * 70)
print("10. WEIGHT OPTIMIZATION (T-07 / A3)")
print("─" * 70)
if ev and ev.get("weight_optimization"):
    wo = ev["weight_optimization"]
    print(f"  Baseline weights (NLP={wo['baseline_weights']['nlp']}, WW={wo['baseline_weights']['wastewater']}, MOB={wo['baseline_weights']['mobility']}): F1={wo['baseline_f1']:.4f}")
    print(f"  Best grid-search (NLP={wo['best_weights']['nlp']}, WW={wo['best_weights']['wastewater']}, MOB={wo['best_weights']['mobility']}): F1={wo['best_f1']:.4f}  (threshold={wo['best_threshold']})")
    print(f"  Total combos tested: {wo['total_combinations_tested']}")
    print(f"  Conclusion: Best manual weight F1 ({wo['best_f1']:.4f}) < Trained GB CV F1 (0.6464) -- trained classifier supersedes manual tuning")

# ── 11. SHAP Feature Importance ────────────────────────────────────────────
print("\n" + "─" * 70)
print("11. SHAP FEATURE IMPORTANCE (T-17)")
print("─" * 70)
if ev and ev.get("feature_importance"):
    fi = ev["feature_importance"]
    print(f"  Method: {fi['method']}")
    for fn in fi['feature_names']:
        print(f"    {fn:<20} Mean|SHAP|={fi['mean_abs_shap'][fn]:.4f}  Normalized={fi['normalized_importance'][fn]:.4f}")
if ev and ev.get("feature_dominance"):
    fd = ev["feature_dominance"]
    od = fd["outbreak_weeks"]
    nd = fd["normal_weeks"]
    print(f"  Outbreak weeks dominance:  NLP {od['nlp_dominant_pct']:.1f}%  Search {od['search_dominant_pct']:.1f}%  Mobility {od['mobility_dominant_pct']:.1f}%")
    print(f"  Normal weeks dominance:    NLP {nd['nlp_dominant_pct']:.1f}%  Search {nd['search_dominant_pct']:.1f}%  Mobility {nd['mobility_dominant_pct']:.1f}%")

# ── 12. Calibration ────────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("12. CALIBRATION (N5)")
print("─" * 70)
if ev and ev.get("calibration"):
    cal = ev["calibration"]
    print(f"  Brier Score:           {cal['brier_score']:.4f}")
    print(f"  Brier Score (climate): {cal['brier_score_climatology']:.4f}")
    print(f"  Brier Skill Score:     {cal['brier_skill_score']:.4f}")
    print(f"  Calibration Slope:     {cal.get('calibration_slope', 'N/A')}")

# ── 13. Missing-Modality Ablation ──────────────────────────────────────────
print("\n" + "─" * 70)
print("13. MISSING-MODALITY ABLATION (N7)")
print("─" * 70)
if ev and ev.get("missing_modality"):
    mm = ev["missing_modality"]
    for key, lbl in [("all", "All modalities"), ("no_nlp", "No NLP"), ("no_mobility", "No Mobility"), ("no_search", "No Symptom Search")]:
        r = mm[key]
        drop = r["relative_f1_drop"] * 100
        print(f"  {lbl:<25} F1={r['f1']:.4f}  AUC={r['auc']:.4f}  Drop={drop:.1f}%")

# ── 14. Cost-Sensitive ─────────────────────────────────────────────────────
print("\n" + "─" * 70)
print("14. COST-SENSITIVE EVALUATION (N6)")
print("─" * 70)
if ev and ev.get("cost_sensitive"):
    cs = ev["cost_sensitive"]
    for mult, label in [("fn_1x", "FN=1x (symmetric)"), ("fn_2x", "FN=2x"), ("fn_5x", "FN=5x"), ("fn_10x", "FN=10x")]:
        r = cs.get(mult, {})
        print(f"  {label:<22} F1={r.get('f1',0):.4f}  Cost={r.get('total_cost',0):>3}  OptThreshold={r.get('optimal_threshold',0):.2f}")

# ── 15. Per-Modality Individual ────────────────────────────────────────────
print("\n" + "─" * 70)
print("15. PER-MODALITY INDIVIDUAL PERFORMANCE")
print("─" * 70)
if ev and ev.get("per_modality"):
    pm = ev["per_modality"]
    for key, label in [("nlp_only", "NLP only"), ("mobility_only", "Mobility only"), ("wastewater_only", "Wastewater proxy only")]:
        m = pm.get(key, {})
        print(f"  {label:<30} F1={m.get('f1_score',0):.4f}  AUC={m.get('roc_auc',0):.4f}  (weight={m.get('weight_in_fusion', 'N/A')})")

# ── 16. Banglish Ablation ──────────────────────────────────────────────────
print("\n" + "─" * 70)
print("16. BANGLISH ABLATION")
print("─" * 70)
if bl:
    print(f"  With Banglish detection:    F1={bl['with_detection']['f1']:.4f}  P={bl['with_detection']['precision']:.4f}  R={bl['with_detection']['recall']:.4f}")
    print(f"  Without Banglish detection: F1={bl['without_detection']['f1']:.4f}  P={bl['without_detection']['precision']:.4f}  R={bl['without_detection']['recall']:.4f}")
    print(f"  F1 improvement: {bl['f1_improvement']:.4f}  (n={bl['n_banglish_samples']} Banglish test samples)")

# ── DONE ───────────────────────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("EXTRACTION COMPLETE — use these numbers in your JMIR paper")
print(f"{'=' * 70}")