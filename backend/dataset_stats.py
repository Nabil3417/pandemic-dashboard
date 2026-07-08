"""
dataset_stats.py — Dataset statistics, cleaning, and LaTeX table generation
for BioGuard AI's multilingual NLP labeled dataset.
"""

import os
import re
import json
import unicodedata
from collections import Counter

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_PATH = "data/nlp_labeled_dataset.csv"
CLEAN_PATH = "data/nlp_labeled_dataset_clean.csv"
SUMMARY_PATH = "data/dataset_summary.json"

LANGUAGE_ORDER = ["en", "bn", "banglish", "hi", "ar", "id", "fr", "es", "pt", "ur", "ms", "ta"]

LANGUAGE_DISPLAY_NAMES = {
    "en": "English",
    "bn": "Bangla",
    "banglish": "Banglish",
    "hi": "Hindi",
    "ar": "Arabic",
    "id": "Indonesian",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "ur": "Urdu",
    "ms": "Malay",
    "ta": "Tamil",
}

MIN_TEXT_LENGTH = 5

# A generic multilingual stopword-ish filter for the "top words" analysis.
# This is intentionally small; the point is just to filter out the most
# common connective/function words so health-signal words rise to the top.
GENERIC_STOPWORDS = {
    "en": {"the", "a", "an", "is", "are", "was", "were", "i", "my", "me", "and", "to", "in",
           "of", "it", "for", "on", "at", "this", "that", "with", "as", "be", "have", "has",
           "had", "not", "no", "just", "so", "but", "or", "we", "you", "he", "she", "they"},
    "bn": set(),
    "banglish": {"ami", "amar", "onek", "hochhe", "jacchi", "kharap", "valo", "kintu",
                 "ache", "hobe", "hoise", "hoy", "na", "ta", "e", "te", "er", "o", "ei",
                 "aj", "kal", "lagbe", "khub"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_whitespace(text):
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    """Simple whitespace + punctuation-strip tokenizer. Works reasonably for
    both Latin-script and Unicode-script (Bangla/Arabic/etc.) text since we
    only split on whitespace and strip common punctuation, not on script."""
    if not isinstance(text, str):
        return []
    text = text.lower()
    # Strip common punctuation but keep unicode letters (Bangla/Arabic/etc.)
    text = re.sub(r"[.,!?;:\"'()\[\]{}<>~`@#$%^&*_+=|\\/]+", " ", text)
    tokens = [t for t in text.split() if len(t) > 1]
    return tokens


def top_words(texts, stopwords, n=10):
    counter = Counter()
    for text in texts:
        for tok in tokenize(text):
            if tok not in stopwords:
                counter[tok] += 1
    return counter.most_common(n)


def safe_div(a, b):
    return round(a / b, 2) if b else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not os.path.exists(DATA_PATH):
        print(f"ERROR: Could not find dataset at {DATA_PATH}")
        return

    df = pd.read_csv(DATA_PATH, encoding="utf-8")

    required_cols = {"text", "language", "label", "source"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"ERROR: Dataset is missing required columns: {missing}")
        return

    print("=" * 70)
    print("BIOGUARD AI — NLP DATASET STATISTICS")
    print("=" * 70)

    # -----------------------------------------------------------------
    # Basic cleanup for analysis (not saved yet — cleaning/saving happens
    # later as its own explicit step, but we need labels as int and text
    # as string to compute stats safely)
    # -----------------------------------------------------------------
    df["text"] = df["text"].astype(str)
    df["language"] = df["language"].astype(str).str.strip().str.lower()
    df["source"] = df["source"].astype(str).str.strip().str.lower()

    # Coerce label to int where possible; drop rows where it fails
    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    bad_labels = df["label"].isna().sum()
    if bad_labels:
        print(f"WARNING: {bad_labels} rows had invalid label values and will be dropped from stats.")
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)

    # -----------------------------------------------------------------
    # 1. Total samples, label breakdown
    # -----------------------------------------------------------------
    total = len(df)
    label_1 = int((df["label"] == 1).sum())
    label_0 = int((df["label"] == 0).sum())

    print(f"\nTotal samples: {total}")
    print(f"  Label 1 (outbreak signal): {label_1} ({safe_div(label_1*100, total)}%)")
    print(f"  Label 0 (normal):          {label_0} ({safe_div(label_0*100, total)}%)")

    # -----------------------------------------------------------------
    # 2. Breakdown by language
    # -----------------------------------------------------------------
    print("\n--- Breakdown by Language ---")
    lang_counts = df["language"].value_counts()
    langs_present = [l for l in LANGUAGE_ORDER if l in lang_counts.index]
    extra_langs = [l for l in lang_counts.index if l not in LANGUAGE_ORDER]
    if extra_langs:
        print(f"NOTE: Found unexpected language codes not in the standard 12: {extra_langs}")

    for lang in langs_present + extra_langs:
        count = int(lang_counts.get(lang, 0))
        display = LANGUAGE_DISPLAY_NAMES.get(lang, lang)
        print(f"  {display:12s} ({lang:8s}): {count}")

    # -----------------------------------------------------------------
    # 3. Cross-table: language x label
    # -----------------------------------------------------------------
    print("\n--- Cross-table: Language x Label ---")
    cross = pd.crosstab(df["language"], df["label"])
    for col in [0, 1]:
        if col not in cross.columns:
            cross[col] = 0
    cross = cross[[0, 1]]
    cross_ordered = cross.reindex(langs_present + extra_langs).fillna(0).astype(int)
    print(f"{'Language':12s} {'Label=0':>10s} {'Label=1':>10s}")
    for lang, row in cross_ordered.iterrows():
        display = LANGUAGE_DISPLAY_NAMES.get(lang, lang)
        print(f"{display:12s} {row[0]:>10d} {row[1]:>10d}")

    # -----------------------------------------------------------------
    # 4. Real vs synthetic breakdown
    # -----------------------------------------------------------------
    print("\n--- Real vs Synthetic ---")
    source_counts = df["source"].value_counts()
    synthetic_count = int(source_counts.get("synthetic", 0))
    real_count = total - synthetic_count
    print(f"  Synthetic: {synthetic_count}")
    print(f"  Real:      {real_count}")
    for src, count in source_counts.items():
        print(f"    - {src}: {count}")

    # -----------------------------------------------------------------
    # 5. Average post length by language
    # -----------------------------------------------------------------
    print("\n--- Average Post Length (characters) by Language ---")
    df["char_len"] = df["text"].apply(len)
    avg_len_by_lang = df.groupby("language")["char_len"].mean()
    for lang in langs_present + extra_langs:
        avg_len = avg_len_by_lang.get(lang, 0)
        display = LANGUAGE_DISPLAY_NAMES.get(lang, lang)
        print(f"  {display:12s}: {avg_len:.1f} chars")

    # -----------------------------------------------------------------
    # 6. Top 10 health-signal words in label=1 posts, by language group
    # -----------------------------------------------------------------
    print("\n--- Top 10 Words in Label=1 Posts (by language group) ---")
    for lang_group in ["en", "bn", "banglish"]:
        subset = df[(df["language"] == lang_group) & (df["label"] == 1)]
        if len(subset) == 0:
            print(f"\n  [{LANGUAGE_DISPLAY_NAMES.get(lang_group, lang_group)}] No label=1 samples found.")
            continue
        stopwords = GENERIC_STOPWORDS.get(lang_group, set())
        words = top_words(subset["text"].tolist(), stopwords, n=10)
        print(f"\n  [{LANGUAGE_DISPLAY_NAMES.get(lang_group, lang_group)}] (n={len(subset)}):")
        for word, count in words:
            print(f"    {word:20s} {count}")

    # -----------------------------------------------------------------
    # CLEANING
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CLEANING DATASET")
    print("=" * 70)

    clean_df = df.copy()
    before = len(clean_df)

    # Normalize whitespace
    clean_df["text"] = clean_df["text"].apply(normalize_whitespace)

    # Remove posts under MIN_TEXT_LENGTH characters
    clean_df = clean_df[clean_df["text"].str.len() >= MIN_TEXT_LENGTH]
    after_len_filter = len(clean_df)

    # Remove exact duplicate texts (keep first occurrence)
    clean_df = clean_df.drop_duplicates(subset=["text"], keep="first")
    after_dedup = len(clean_df)

    print(f"  Rows before cleaning:              {before}")
    print(f"  Removed (under {MIN_TEXT_LENGTH} chars):        {before - after_len_filter}")
    print(f"  Removed (exact duplicates):        {after_len_filter - after_dedup}")
    print(f"  Rows after cleaning:               {after_dedup}")

    # Drop helper column before saving
    clean_df = clean_df.drop(columns=["char_len"], errors="ignore")

    os.makedirs(os.path.dirname(CLEAN_PATH), exist_ok=True)
    clean_df.to_csv(CLEAN_PATH, index=False, encoding="utf-8")
    print(f"\n  Saved cleaned dataset to: {CLEAN_PATH}")

    # -----------------------------------------------------------------
    # SAVE SUMMARY JSON (based on ORIGINAL uncleaned stats, per spec)
    # -----------------------------------------------------------------
    by_language = {}
    for lang in langs_present + extra_langs:
        lang_df = df[df["language"] == lang]
        by_language[lang] = {
            "total": int(len(lang_df)),
            "label_1": int((lang_df["label"] == 1).sum()),
            "label_0": int((lang_df["label"] == 0).sum()),
            "avg_len": round(float(lang_df["char_len"].mean()) if len(lang_df) else 0.0, 1),
        }

    summary = {
        "total": total,
        "label_1": label_1,
        "label_0": label_0,
        "real_posts": real_count,
        "synthetic_posts": synthetic_count,
        "by_language": by_language,
    }

    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved summary JSON to: {SUMMARY_PATH}")

    # -----------------------------------------------------------------
    # LATEX TABLE
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("LATEX TABLE (copy-paste ready)")
    print("=" * 70 + "\n")

    latex_lines = []
    latex_lines.append(r"\begin{table}[h]")
    latex_lines.append(r"\centering")
    latex_lines.append(r"\caption{Multilingual Health Signal Dataset Statistics}")
    latex_lines.append(r"\label{tab:dataset}")
    latex_lines.append(r"\begin{tabular}{lrrrr}")
    latex_lines.append(r"\hline")
    latex_lines.append(r"Language & Total & Outbreak (1) & Normal (0) & Avg Len \\")
    latex_lines.append(r"\hline")

    for lang in langs_present + extra_langs:
        stats = by_language[lang]
        display = LANGUAGE_DISPLAY_NAMES.get(lang, lang.capitalize())
        latex_lines.append(
            f"{display} & {stats['total']} & {stats['label_1']} & "
            f"{stats['label_0']} & {stats['avg_len']} \\\\"
        )

    latex_lines.append(r"\hline")
    latex_lines.append(
        rf"\textbf{{Total}} & {total} & {label_1} & {label_0} & "
        rf"{round(float(df['char_len'].mean()), 1)} \\"
    )
    latex_lines.append(r"\hline")
    latex_lines.append(r"\end{tabular}")
    latex_lines.append(r"\end{table}")

    latex_table = "\n".join(latex_lines)
    print(latex_table)
    
    latex_file = "data/dataset_table.tex"
    with open(latex_file, "w", encoding="utf-8") as f:
        f.write(latex_table)
    print(f"  Saved LaTeX table to: {latex_file}")

    print("\nDone.")


if __name__ == "__main__":
    main()
