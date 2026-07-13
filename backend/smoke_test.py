"""
BioGuard AI — Smoke Test
========================
Quick health-check script. Run BEFORE any demo or paper submission.
Verifies: data files, model artifacts, MongoDB, Flask endpoints, JSON outputs.

Usage:
    cd backend
    python smoke_test.py
"""

import os
import sys
import json
import glob

PASS = 0
FAIL = 0
WARN = 0

def check(name, condition, detail=""):
    global PASS, FAIL, WARN
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")

def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  ⚠️  {name}  {detail}")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
MODELS = os.path.join(BASE, "models")

print("=" * 60)
print("BioGuard AI — Smoke Test")
print("=" * 60)

# ── 1. Data Files ─────────────────────────────────────────────────────────
print("\n[1] Data Files")
check("outbreak_ground_truth.csv", os.path.exists(os.path.join(DATA, "outbreak_ground_truth.csv")))
check("zones.json", os.path.exists(os.path.join(DATA, "zones.json")))
check("corridors.json", os.path.exists(os.path.join(DATA, "corridors.json")))
check("evaluation_results.json", os.path.exists(os.path.join(DATA, "evaluation_results.json")))
check("fusion_training_results.json", os.path.exists(os.path.join(DATA, "fusion_training_results.json")))
check("nlp_evaluation_results.json", os.path.exists(os.path.join(DATA, "nlp_evaluation_results.json")))
check("finetuning_results.json", os.path.exists(os.path.join(DATA, "finetuning_results.json")))
check("banglish_ablation.json", os.path.exists(os.path.join(DATA, "banglish_ablation.json")))
check("dataset_summary.json", os.path.exists(os.path.join(DATA, "dataset_summary.json")))
check("dhaka_zone_mobility_2020_2022.csv", os.path.exists(os.path.join(DATA, "dhaka_zone_mobility_2020_2022.csv")))
check("dhaka_zone_symptom_trends.csv", os.path.exists(os.path.join(DATA, "dhaka_zone_symptom_trends.csv")))

# ── 2. Model Artifacts ────────────────────────────────────────────────────
print("\n[2] Model Artifacts")
check("fusion_classifier.pkl", os.path.exists(os.path.join(MODELS, "fusion_classifier.pkl")))
check("fusion_scaler.pkl", os.path.exists(os.path.join(MODELS, "fusion_scaler.pkl")))
finetuned_dir = os.path.join(MODELS, "bioguard_xlm_finetuned")
check("bioguard_xlm_finetuned/ directory", os.path.isdir(finetuned_dir))
if os.path.isdir(finetuned_dir):
    safetensors = glob.glob(os.path.join(finetuned_dir, "*.safetensors"))
    check("  safetensors model files", len(safetensors) > 0, f"found {len(safetensors)}")
else:
    warn("  safetensors files", "directory missing, skipping")

# ── 3. JSON Integrity ─────────────────────────────────────────────────────
print("\n[3] JSON Integrity")

def load_json_safe(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        return None

ev = load_json_safe(os.path.join(DATA, "evaluation_results.json"))
check("evaluation_results.json parses", ev is not None)
if ev:
    check("  has combined_model key", "combined_model" in ev)
    check("  has combined_model_trained key", "combined_model_trained" in ev)
    check("  has weight_optimization key (A3)", "weight_optimization" in ev)
    if ev.get("combined_model_trained"):
        tm = ev["combined_model_trained"]
        check("  trained model has paper_notes (A2)", tm.get("paper_notes") is not None)
        if tm.get("paper_notes"):
            pn = tm["paper_notes"]
            check(f"    cv_5fold_f1 = {pn.get('cv_5fold_f1', 'MISSING')}", pn.get("cv_5fold_f1") is not None)
    check("  has walk_forward_cv (N3)", "walk_forward_cv" in ev)
    check("  has per_disease_breakdown (N1)", "per_disease_breakdown" in ev)
    check("  has n2_statistical_significance (N2)", "n2_statistical_significance" in ev)
    check("  has missing_modality (N7)", "missing_modality" in ev)

ft = load_json_safe(os.path.join(DATA, "fusion_training_results.json"))
check("fusion_training_results.json parses", ft is not None)
if ft:
    check("  has gradient_boosting key", "gradient_boosting" in ft)
    gb = ft.get("gradient_boosting", {})
    check(f"    cv_f1_mean = {gb.get('cv_f1_mean', 'MISSING')}", gb.get("cv_f1_mean") is not None)
    check(f"    cv_auc_mean = {gb.get('cv_auc_mean', 'MISSING')}", gb.get("cv_auc_mean") is not None)

# ── 4. MongoDB Connection ─────────────────────────────────────────────────
print("\n[4] MongoDB Connection")
try:
    from database import client, db
    check("MongoDB client connected", True)
    # Quick ping
    client.admin.command('ping')
    check("MongoDB ping OK", True)

    colls = db.list_collection_names()
    for c in ["social_media_posts", "risk_snapshots", "trends_data", "iedcr_reports", "wdzmi_results"]:
        check(f"  collection '{c}' exists", c in colls)

    # Quick count checks
    for c, label in [("social_media_posts", "social posts"), ("risk_snapshots", "risk snapshots"),
                      ("trends_data", "trends records"), ("iedcr_reports", "IEDCR reports")]:
        try:
            count = db[c].count_documents({})
            if count > 0:
                check(f"  {label}: {count} docs", True)
            else:
                warn(f"  {label}: 0 docs", "collection is empty")
        except Exception:
            warn(f"  {label}: count failed", "permission or network issue")
except SystemExit:
    check("MongoDB client", False, "database.py called exit(1) — check MONGO_URI env var")
except Exception as e:
    check("MongoDB client", False, str(e)[:80])

# ── 5. Key Python Imports ─────────────────────────────────────────────────
print("\n[5] Key Python Imports")
for mod, pkg in [
    ("sklearn", "scikit-learn"), ("sklearn.ensemble", "scikit-learn"),
    ("sklearn.preprocessing", "scikit-learn"), ("sklearn.model_selection", "scikit-learn"),
    ("joblib", "joblib"), ("flask", "flask"), ("flask_cors", "flask-cors"),
    ("pymongo", "pymongo"), ("numpy", "numpy"), ("pandas", "pandas"),
    ("scipy", "scipy"), ("shap", "shap"), ("matplotlib", "matplotlib"),
    ("apscheduler", "apscheduler"), ("statsmodels", "statsmodels"),
]:
    try:
        __import__(mod)
        check(f"  {pkg}", True)
    except ImportError:
        check(f"  {pkg}", False, "not installed")

# ── 6. Model Loading ──────────────────────────────────────────────────────
print("\n[6] Model Loading")
try:
    import joblib
    model = joblib.load(os.path.join(MODELS, "fusion_classifier.pkl"))
    scaler = joblib.load(os.path.join(MODELS, "fusion_scaler.pkl"))
    check("fusion_classifier.pkl loads", True)
    check(f"  model type: {type(model).__name__}", True)
    check("fusion_scaler.pkl loads", True)
    # Quick predict test
    import numpy as np
    X_test = np.array([[50.0, 60.0, 30.0]])
    X_scaled = scaler.transform(X_test)
    proba = model.predict_proba(X_scaled)[:, 1]
    check(f"  predict_proba works: {proba[0]:.4f}", 0.0 <= proba[0] <= 1.0)
except Exception as e:
    check("model loading", False, str(e)[:80])

# ── 7. Flask App Import ───────────────────────────────────────────────────
print("\n[7] Flask App Import")
try:
    sys.path.insert(0, BASE)
    from app import app as flask_app
    check("Flask app imports", True)
    # Count routes
    routes = [rule.rule for rule in flask_app.url_map.iter_rules() if rule.rule != '/static/<path:filename>']
    check(f"  {len(routes)} routes registered", len(routes) >= 15)
    # Check key routes exist
    for r in ["/", "/api/risk-status", "/api/evaluation-results", "/api/forecast",
              "/api/system-summary", "/api/fusion-info", "/api/feature-importance",
              "/api/mobility", "/api/signals"]:
        check(f"  route {r}", r in routes)
except SystemExit:
    check("Flask app import", False, "database.py exit(1) — fix MONGO_URI first")
except Exception as e:
    check("Flask app import", False, str(e)[:100])

# ── 8. Credential Safety ──────────────────────────────────────────────────
print("\n[8] Credential Safety")
cred_files = ["backend/data_collectors/dzmi.py", "backend/data_collectors/mobility_repository.py",
              "backend/test_dzmi_diag.py"]
found_creds = False
for cf in cred_files:
    fpath = os.path.join(BASE, "..", cf)
    if not os.path.exists(fpath):
        fpath = os.path.join(BASE, cf)
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if "mongodb+srv://" in content and "cluster0" in content and "@" in content:
            check(f"  {os.path.basename(cf)}: NO HARDCODED CREDS", False, "contains mongodb+srv connection string")
            found_creds = True
if not found_creds:
    check("  No hardcoded MongoDB URIs found", True)

# ── 9. Paper Figures ──────────────────────────────────────────────────────
print("\n[9] Paper Figures")
fig_dir = os.path.join(BASE, "paper_figures")
if os.path.isdir(fig_dir):
    figs = glob.glob(os.path.join(fig_dir, "*.png"))
    check(f"  {len(figs)} figure(s) in paper_figures/", len(figs) > 0)
    for fig in figs:
        size_kb = os.path.getsize(fig) / 1024
        check(f"    {os.path.basename(fig)} ({size_kb:.0f} KB)", size_kb > 1)
else:
    warn("  paper_figures/ directory", "does not exist — run evaluate.py first")

# ── Summary ───────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
total = PASS + FAIL + WARN
print(f"RESULTS:  ✅ {PASS} passed   ❌ {FAIL} failed   ⚠️  {WARN} warnings  ({total} total)")
if FAIL == 0:
    print("All checks passed — system is ready for demo/paper submission.")
elif FAIL <= 3:
    print(f"Minor issues detected ({FAIL} failures) — review above.")
else:
    print(f"⚠️  {FAIL} failures found — fix before submitting!")
print(f"{'=' * 60}")

sys.exit(FAIL)