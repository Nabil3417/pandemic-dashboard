"""
BioGuard AI — Fine-Tune XLM-RoBERTa for Health Signal Detection
================================================================
Takes the labeled CSV (nlp_labeled_dataset.csv) and fine-tunes
cardiffnlp/twitter-xlm-roberta-base-sentiment for binary
health-signal classification (0 = not outbreak, 1 = outbreak signal).

Outputs:
  - backend/models/bioguard_xlm_finetuned/   (model weights)
  - backend/data/finetuning_results.json      (base vs fine-tuned metrics)
  - backend/data/nlp_test_split.csv           (held-out test set for evaluate_nlp.py)

Runtime: 15-30 minutes on CPU. Do not close the terminal.
"""

import os
import sys
import json
import time
import warnings
from datetime import datetime

import numpy as np

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════════════
# PART 1: CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# Resolve paths relative to THIS script's location (works from any cwd)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_NAME    = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
SAVE_PATH     = os.path.join(_SCRIPT_DIR, "models", "bioguard_xlm_finetuned")
DATA_PATH     = os.path.join(_SCRIPT_DIR, "data", "nlp_labeled_dataset.csv")
RESULTS_PATH  = os.path.join(_SCRIPT_DIR, "data", "finetuning_results.json")
TEST_SPLIT    = os.path.join(_SCRIPT_DIR, "data", "nlp_test_split.csv")

NUM_EPOCHS      = 3
BATCH_SIZE      = 16
EVAL_BATCH_SIZE = 32
LEARNING_RATE   = 2e-5
RANDOM_STATE    = 42
MAX_LENGTH      = 128

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS — with graceful handling
# ══════════════════════════════════════════════════════════════════════════════

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Run: pip install pandas")
    sys.exit(1)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    from torch.optim import AdamW
except ImportError:
    print("ERROR: PyTorch not installed. Run: pip install torch")
    sys.exit(1)

try:
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        get_linear_schedule_with_warmup,
    )
except ImportError:
    print("ERROR: transformers not installed. Run: pip install transformers")
    sys.exit(1)

try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
        f1_score, roc_auc_score,
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
# PART 2: DATA LOADING AND SPLITTING
# ══════════════════════════════════════════════════════════════════════════════

def load_and_split_data(data_path):
    """
    Load CSV, clean, and create stratified 70/15/15 split.
    Returns train_df, val_df, test_df.
    """
    if not os.path.exists(data_path):
        print(f"ERROR: Dataset not found at {data_path}")
        print("Run S-01 and S-02 first to generate the labeled dataset.")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows from {data_path}")

    if len(df) < 50:
        print(f"ERROR: Dataset too small ({len(df)} rows). Need at least 50.")
        sys.exit(1)

    # Drop nulls
    before = len(df)
    df = df.dropna(subset=['text', 'language', 'label'])
    df = df[df['text'].notna()]
    if len(df) < before:
        print(f"Dropped {before - len(df)} rows with null values")

    # Remove texts under 5 chars
    before = len(df)
    df = df[df['text'].str.len() >= 5]
    if len(df) < before:
        print(f"Dropped {before - len(df)} rows with text < 5 chars")

    # Remove duplicates
    before = len(df)
    df = df.drop_duplicates(subset=['text'])
    if len(df) < before:
        print(f"Dropped {before - len(df)} duplicate rows")

    # Ensure label is int
    df['label'] = df['label'].astype(int)

    # Stratified split: 70% train, 15% val, 15% test
    train_val_df, test_df = train_test_split(
        df,
        test_size=0.15,
        stratify=df['label'],
        random_state=RANDOM_STATE,
    )

    train_df, val_df = train_test_split(
        train_val_df,
        test_size=0.1765,
        stratify=train_val_df['label'],
        random_state=RANDOM_STATE,
    )

    # Save test split for evaluate_nlp.py
    test_df.to_csv(TEST_SPLIT, index=False)
    print(f"Test split saved to {TEST_SPLIT}")

    positive_pct = train_df['label'].mean() * 100
    print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)} "
          f"| Label balance: {positive_pct:.1f}% positive")

    return train_df, val_df, test_df


# ══════════════════════════════════════════════════════════════════════════════
# PART 3: PYTORCH DATASET CLASS
# ══════════════════════════════════════════════════════════════════════════════

class HealthSignalDataset(Dataset):
    """
    PyTorch Dataset for health signal text classification.
    Tokenizes text using AutoTokenizer with max_length=128.
    """

    def __init__(self, texts, labels, tokenizer):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = int(self.labels[idx])

        encoding = self.tokenizer(
            text,
            max_length=MAX_LENGTH,
            truncation=True,
            padding='max_length',
            return_tensors='pt',
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long),
        }


def create_dataloaders(train_df, val_df, test_df, tokenizer):
    """Create DataLoaders for train/val/test splits."""
    train_dataset = HealthSignalDataset(
        train_df['text'].values, train_df['label'].values, tokenizer
    )
    val_dataset = HealthSignalDataset(
        val_df['text'].values, val_df['label'].values, tokenizer
    )
    test_dataset = HealthSignalDataset(
        test_df['text'].values, test_df['label'].values, tokenizer
    )

    train_loader = DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_dataset, batch_size=EVAL_BATCH_SIZE, shuffle=False, num_workers=0
    )
    test_loader = DataLoader(
        test_dataset, batch_size=EVAL_BATCH_SIZE, shuffle=False, num_workers=0
    )

    return train_loader, val_loader, test_loader


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: MODEL LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_model_and_tokenizer():
    """Load XLM-RoBERTa for sequence classification (2 labels)."""
    print(f"Loading base model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        ignore_mismatched_sizes=True,
    )

    device = torch.device('cpu')
    model = model.to(device)
    print(f"Training on CPU. Estimated time: 15-30 min. Do not close terminal.")

    return model, tokenizer, device


# ══════════════════════════════════════════════════════════════════════════════
# PART 5: OPTIMIZER AND SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════

def create_optimizer_and_scheduler(model, train_loader):
    """Create AdamW optimizer with linear warmup scheduler."""
    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=0.01,
    )

    total_steps = len(train_loader) * NUM_EPOCHS
    warmup_steps = len(train_loader)

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    return optimizer, scheduler


# ══════════════════════════════════════════════════════════════════════════════
# PART 6: TRAINING LOOP (manual, no HuggingFace Trainer)
# ══════════════════════════════════════════════════════════════════════════════

def train_one_epoch(model, train_loader, optimizer, scheduler, device, epoch):
    """Train for one epoch. Returns average training loss."""
    model.train()
    total_loss = 0.0
    num_batches = len(train_loader)
    criterion = nn.CrossEntropyLoss()

    iterator = tqdm(train_loader, desc=f"Epoch {epoch+1}/{NUM_EPOCHS}") \
        if HAS_TQDM else train_loader

    for batch_idx, batch in enumerate(iterator):
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        optimizer.zero_grad()

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        logits = outputs.logits
        loss = criterion(logits, labels)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

        if not HAS_TQDM and (batch_idx + 1) % 10 == 0:
            print(f"  Epoch {epoch+1}/{NUM_EPOCHS} | Batch {batch_idx+1}/{num_batches} "
                  f"| Loss: {loss.item():.4f}")

    avg_loss = total_loss / num_batches
    return avg_loss


def evaluate(model, data_loader, device):
    """
    Run evaluation. Returns (loss, accuracy, f1, all_labels, all_preds, all_probs).
    """
    model.eval()
    total_loss = 0.0
    all_labels = []
    all_preds = []
    all_probs = []
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for batch in data_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            logits = outputs.logits
            loss = criterion(logits, labels)
            total_loss += loss.item()

            probs = torch.softmax(logits, dim=1)
            preds = torch.argmax(logits, dim=1)

            all_labels.extend(labels.cpu().numpy())
            all_preds.extend(preds.cpu().numpy())
            all_probs.extend(probs[:, 1].cpu().numpy())

    avg_loss = total_loss / len(data_loader)
    accuracy = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average='binary', zero_division=0)

    return avg_loss, accuracy, f1, all_labels, all_preds, all_probs


def training_loop(model, train_loader, val_loader, device, optimizer, scheduler):
    """
    Full training loop across NUM_EPOCHS.
    Saves best model (lowest val_loss) to SAVE_PATH.
    """
    best_val_loss = float('inf')
    print(f"\n{'='*60}")
    print(f"  STARTING FINE-TUNING: {NUM_EPOCHS} epochs")
    print(f"{'='*60}\n")

    for epoch in range(NUM_EPOCHS):
        t0 = time.time()

        train_loss = train_one_epoch(
            model, train_loader, optimizer, scheduler, device, epoch
        )

        val_loss, val_acc, val_f1, _, _, _ = evaluate(
            model, val_loader, device
        )

        elapsed = time.time() - t0
        print(f"Epoch {epoch+1}/{NUM_EPOCHS} complete | "
              f"Val Loss: {val_loss:.3f} | "
              f"Val Acc: {val_acc:.3f} | "
              f"Val F1: {val_f1:.3f} | "
              f"Time: {elapsed:.0f}s")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            os.makedirs(SAVE_PATH, exist_ok=True)
            model.save_pretrained(SAVE_PATH)
            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            tokenizer.save_pretrained(SAVE_PATH)
            print(f"  Best model saved (val_loss={val_loss:.3f})")

    print(f"\n{'='*60}")
    print(f"  FINE-TUNING COMPLETE")
    print(f"  Best validation loss: {best_val_loss:.3f}")
    print(f"  Model saved to: {SAVE_PATH}")
    print(f"{'='*60}")

    return best_val_loss


# ══════════════════════════════════════════════════════════════════════════════
# PART 7: TEST EVALUATION (Base vs Fine-Tuned)
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(labels, preds, probs):
    """Compute all metrics for a set of predictions."""
    acc = accuracy_score(labels, preds)
    prec = precision_score(labels, preds, average='binary', zero_division=0)
    rec = recall_score(labels, preds, average='binary', zero_division=0)
    f1 = f1_score(labels, preds, average='binary', zero_division=0)

    try:
        auc = roc_auc_score(labels, probs)
    except ValueError:
        auc = 0.0

    return {
        'accuracy': round(float(acc), 4),
        'precision': round(float(prec), 4),
        'recall': round(float(rec), 4),
        'f1': round(float(f1), 4),
        'roc_auc': round(float(auc), 4),
    }


def evaluate_model_on_test(model, test_loader, device, test_df):
    """
    Evaluate a model on the test set.
    Returns overall metrics + per-language metrics.
    """
    _, _, _, all_labels, all_preds, all_probs = evaluate(
        model, test_loader, device
    )

    overall = compute_metrics(all_labels, all_preds, all_probs)

    per_language = {}
    languages = test_df['language'].unique()

    for lang in sorted(languages):
        lang_mask = test_df['language'].values == lang
        lang_labels = np.array(all_labels)[lang_mask]
        lang_preds = np.array(all_preds)[lang_mask]
        lang_probs = np.array(all_probs)[lang_mask]

        if len(lang_labels) < 5:
            print(f"  WARNING: Skipping '{lang}' — only {len(lang_labels)} test samples (need >= 5)")
            continue

        lang_metrics = compute_metrics(lang_labels, lang_preds, lang_probs)
        per_language[lang] = lang_metrics

    return overall, per_language


def print_comparison_table(base_results, finetuned_results):
    """Print the base vs fine-tuned comparison table."""
    print(f"\n{'='*60}")
    print("RESULTS: BASE vs FINE-TUNED XLM-RoBERTa")
    print(f"{'='*60}")

    rows = []

    b_f1 = base_results['overall']['f1']
    f_f1 = finetuned_results['overall']['f1']
    rows.append(('Overall F1', b_f1, f_f1))

    for lang in ['en', 'bn', 'banglish', 'hi', 'ar', 'id', 'fr', 'es', 'pt', 'ur', 'ms', 'ta']:
        if lang in finetuned_results['per_language']:
            f_val = finetuned_results['per_language'][lang]['f1']
            b_val = base_results['per_language'].get(lang, {}).get('f1', 0.0)
            name = lang.capitalize()
            if lang == 'bn':
                name = 'Bangla'
            elif lang == 'en':
                name = 'English'
            elif lang == 'banglish':
                name = 'Banglish'
            rows.append((f'{name} F1', b_val, f_val))

    b_auc = base_results['overall']['roc_auc']
    f_auc = finetuned_results['overall']['roc_auc']
    rows.append(('ROC-AUC', b_auc, f_auc))

    print(f"{'Metric':<20} {'Base':>10} {'Fine-Tuned':>12} {'Delta':>10}")
    print(f"{'-'*55}")

    for name, base_val, ft_val in rows:
        delta = ft_val - base_val
        sign = '+' if delta >= 0 else ''
        print(f"{name:<20} {base_val:>10.3f} {ft_val:>12.3f} {sign}{delta:>9.3f}")

    print(f"{'='*60}")


def run_test_comparison(test_loader, test_df, device):
    """
    Evaluate BOTH the base model and fine-tuned model on the test set.
    Returns (base_results_dict, finetuned_results_dict).
    """
    print("\nEvaluating FINE-TUNED model on test set...")
    finetuned_model = AutoModelForSequenceClassification.from_pretrained(SAVE_PATH)
    finetuned_model = finetuned_model.to(device)
    finetuned_model.eval()

    ft_overall, ft_per_lang = evaluate_model_on_test(
        finetuned_model, test_loader, device, test_df
    )
    finetuned_results = {'overall': ft_overall, 'per_language': ft_per_lang}

    del finetuned_model
    import gc
    gc.collect()

    print("\nEvaluating BASE model on test set...")
    base_model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=2, ignore_mismatched_sizes=True
    )
    base_model = base_model.to(device)
    base_model.eval()

    base_overall, base_per_lang = evaluate_model_on_test(
        base_model, test_loader, device, test_df
    )
    base_results = {'overall': base_overall, 'per_language': base_per_lang}

    del base_model
    gc.collect()

    print_comparison_table(base_results, finetuned_results)

    return base_results, finetuned_results


# ══════════════════════════════════════════════════════════════════════════════
# PART 8: SAVE RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def save_results(base_results, finetuned_results, train_df, val_df, test_df):
    """Save comprehensive results to JSON."""
    results = {
        'base_model': base_results,
        'finetuned_model': finetuned_results,
        'improvement': {
            'overall_f1_delta': round(
                finetuned_results['overall']['f1'] - base_results['overall']['f1'], 4
            ),
            'banglish_f1_delta': round(
                finetuned_results['per_language'].get('banglish', {}).get('f1', 0) -
                base_results['per_language'].get('banglish', {}).get('f1', 0), 4
            ),
            'auc_delta': round(
                finetuned_results['overall']['roc_auc'] - base_results['overall']['roc_auc'], 4
            ),
        },
        'training_config': {
            'epochs': NUM_EPOCHS,
            'batch_size': BATCH_SIZE,
            'learning_rate': LEARNING_RATE,
            'train_samples': int(len(train_df)),
            'val_samples': int(len(val_df)),
            'test_samples': int(len(test_df)),
            'max_length': MAX_LENGTH,
            'random_state': RANDOM_STATE,
        },
        'model_saved_at': SAVE_PATH,
        'base_model_name': MODEL_NAME,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {RESULTS_PATH}")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  BioGuard AI — XLM-RoBERTa Fine-Tuning")
    print("  Health Signal Detection (Binary Classification)")
    print("=" * 60)
    print(f"  Model: {MODEL_NAME}")
    print(f"  Epochs: {NUM_EPOCHS} | Batch: {BATCH_SIZE} | LR: {LEARNING_RATE}")
    print(f"  Device: CPU")
    print(f"  Data:   {DATA_PATH}")
    print("=" * 60)
    print()

    # Step 1: Load and split data
    train_df, val_df, test_df = load_and_split_data(DATA_PATH)
    print()

    # Step 2: Load model and tokenizer
    model, tokenizer, device = load_model_and_tokenizer()
    print()

    # Step 3: Create data loaders
    train_loader, val_loader, test_loader = create_dataloaders(
        train_df, val_df, test_df, tokenizer
    )

    # Step 4: Create optimizer and scheduler
    optimizer, scheduler = create_optimizer_and_scheduler(model, train_loader)
    print(f"Optimizer: AdamW (lr={LEARNING_RATE}, weight_decay=0.01)")
    print(f"Scheduler: Linear warmup ({len(train_loader)} warmup steps, "
          f"{len(train_loader) * NUM_EPOCHS} total steps)")
    print()

    # Step 5: Train
    training_loop(model, train_loader, val_loader, device, optimizer, scheduler)

    # Step 6: Test comparison (base vs fine-tuned)
    base_results, finetuned_results = run_test_comparison(
        test_loader, test_df, device
    )

    # Step 7: Save results
    save_results(base_results, finetuned_results, train_df, val_df, test_df)

    # Summary
    print(f"\n{'='*60}")
    print("  FINE-TUNING SUMMARY")
    print(f"{'='*60}")
    print(f"  Base model F1:     {base_results['overall']['f1']:.3f}")
    print(f"  Fine-tuned F1:     {finetuned_results['overall']['f1']:.3f}")
    delta = finetuned_results['overall']['f1'] - base_results['overall']['f1']
    sign = '+' if delta >= 0 else ''
    print(f"  Improvement:        {sign}{delta:.3f}")
    print(f"  ROC-AUC:            {finetuned_results['overall']['roc_auc']:.3f}")
    print(f"\n  Model saved to:    {SAVE_PATH}/")
    print(f"  Results saved to:  {RESULTS_PATH}")
    print(f"  Test split saved:  {TEST_SPLIT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()