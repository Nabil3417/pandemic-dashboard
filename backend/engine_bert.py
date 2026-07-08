"""
BioGuard AI — Multi-Lingual Symptom Detection Engine
=====================================================
Architecture:
  - XLM-RoBERTa (cardiffnlp/twitter-xlm-roberta-base-sentiment)
      → English + 103 other languages (primary model)
  - BanglaBERT  (same XLM-RoBERTa, second instance)
      → Bangla & Banglish (ensemble partner)
  - Keyword Boost → amplifies health signal detection
  - Keyword-Only Fallback → works without torch/transformers

Supports 104 languages. Designed for CPU deployment.
Gracefully degrades to keyword-only mode if torch is unavailable.
"""
import os
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    if os.path.exists(torch_lib):
        os.add_dll_directory(torch_lib)
except Exception:
    pass

import re

# ── Graceful import: torch/transformers may be broken on Windows ──
_transformers_available = False
_pipeline_func = None

try:
    from transformers import pipeline
    _transformers_available = True
except (OSError, ImportError, Exception) as e:
    print(f"⚠️  transformers/torch import failed: {e}")
    print("   → Engine will run in KEYWORD-ONLY mode (no ML model).")
    print("   → To fix: install Visual C++ Redistributable 2019-2022 from")
    print("      https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist")
    print("      then reinstall: pip install torch --index-url https://download.pytorch.org/whl/cpu")

try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    _langdetect_available = True
except ImportError:
    _langdetect_available = False

if _langdetect_available:
    DetectorFactory.seed = 42

# ─────────────────────────────────────────────────────────────
# HEALTH SYMPTOM KEYWORDS PER LANGUAGE
# ─────────────────────────────────────────────────────────────

SYMPTOM_KEYWORDS = {
    'en': [
        'fever', 'sick', 'ill', 'hospital', 'flu', 'cough', 'outbreak',
        'infection', 'virus', 'symptom', 'medicine', 'doctor', 'clinic',
        'patient', 'disease', 'health', 'dengue', 'cholera', 'epidemic',
        'pandemic', 'vaccination', 'vaccine', 'death', 'infected', 'vomit',
        'diarrhea', 'breathless', 'pneumonia', 'quarantine', 'isolation',
        'positive', 'tested', 'covid', 'corona', 'monkeypox', 'mpox',
        'icu', 'emergency', 'ward', 'admitted', 'discharge', 'outbreak',
    ],
    'bn': [
        'জ্বর', 'কাশি', 'হাসপাতাল', 'অসুস্থ', 'ডাক্তার', 'ভাইরাস',
        'রোগ', 'ঔষধ', 'সর্দি', 'ক্লিনিক', 'রোগী', 'স্বাস্থ্য',
        'ইনফেকশন', 'করোনা', 'ফ্লু', 'ডেঙ্গু', 'কলেরা', 'মহামারী',
        'টিকা', 'মৃত্যু', 'আক্রান্ত', 'চিকিৎসা', 'সংক্রমণ',
        'প্রাদুর্ভাব', 'শ্বাসকষ্ট', 'বমি', 'ডায়রিয়া', 'নিউমোনিয়া',
        'কোয়ারেন্টাইন', 'আইসোলেশন', 'পজিটিভ', 'টেস্ট', 'চিকিৎসক',
        'স্বাস্থ্যসেবা', 'হৃদরোগ', 'ক্যান্সার', 'ডায়াবেটিস',
    ],
    'hi': [
        'बुखार', 'बीमार', 'अस्पताल', 'खांसी', 'वायरस', 'संक्रमण',
        'डॉक्टर', 'दवा', 'मरीज', 'बीमारी', 'स्वास्थ्य', 'महामारी',
        'टीका', 'मृत्यु', 'कोरोना', 'डेंगू', 'निमोनिया', 'बीमारी',
    ],
    'ar': [
        'حمى', 'مريض', 'مستشفى', 'سعال', 'فيروس', 'عدوى',
        'طبيب', 'دواء', 'مرض', 'صحة', 'وباء', 'لقاح', 'كورونا',
    ],
    'pt': [
        'febre', 'doente', 'hospital', 'tosse', 'vírus', 'infecção',
        'médico', 'remédio', 'paciente', 'doença', 'saúde', 'pandemia',
        'vacina', 'covid', 'dengue', 'pneumonia',
    ],
    'fr': [
        'fièvre', 'malade', 'hôpital', 'toux', 'virus', 'infection',
        'médecin', 'médicament', 'patient', 'maladie', 'santé',
        'pandémie', 'vaccin', 'covid', 'pneumonie',
    ],
    'es': [
        'fiebre', 'enfermo', 'hospital', 'tos', 'virus', 'infección',
        'médico', 'medicamento', 'paciente', 'enfermedad', 'salud',
        'pandemia', 'vacuna', 'covid', 'dengue', 'neumonía',
    ],
    'id': [
        'demam', 'sakit', 'rumah sakit', 'batuk', 'virus', 'infeksi',
        'dokter', 'obat', 'pasien', 'penyakit', 'kesehatan', 'pandemi',
        'vaksin', 'covid', 'corona',
    ],
    'ur': [
        'بخار', 'کھانسی', 'وائرس', 'اسپتال', 'بیمار', 'وبا',
        'انفیکشن', 'مریض', 'بیماری', 'صحت', 'ڈاکٹر', 'دوا',
        'کورونا', 'ڈینگی', 'نمونیا', 'ہیضہ', 'وبائی مرض',
        'ویکسین', 'موت', 'متاثر', 'قرنطینہ', 'آئی سی یو',
        'علامات', 'علاج', 'ہسپتال',
    ],
    'ms': [
        'demam', 'batuk', 'virus', 'hospital', 'sakit', 'jangkitan',
        'wabak', 'pesakit', 'penyakit', 'kesihatan', 'doktor', 'ubat',
        'covid', 'denggi', 'pneumonia', 'taun', 'pandemik', 'vaksin',
        'kematian', 'dijangkiti', 'kuarantin', 'icu', 'gejala',
        'rawatan', 'kluster', 'kes baharu', 'positif', 'respiratori',
    ],
    'ta': [
        'காய்ச்சல்', 'இருமல்', 'வைரஸ்', 'மருத்துவமனை', 'நோய்',
        'தொற்று', 'நோயாளி', 'மருத்துவர்', 'மருந்து', 'நோய்க்காட்டி',
        'தொற்றுநோய்', 'மோய்', 'காலரா', 'தொற்றுநோய்', 'தடுப்பூசி',
        'இறப்பு', 'தனிமைப்படுத்தல்', 'ஐசியு', 'அறிகுறிகள்',
        'சிகிச்சை', 'புரல்', 'சுகாதாரம்',
    ],
}

UNIVERSAL_KEYWORDS = [
    'covid', 'corona', 'covid-19', 'pandemic', 'epidemic', 'who',
    'hospital', 'icu', 'pcr', 'vaccine', 'virus', 'mpox', 'monkeypox',
    'lockdown', 'quarantine', 'outbreak', 'infected',
]

# Banglish Roman words commonly used by Bangladeshis
BANGLISH_MARKERS = [
    'ami', 'amar', 'ache', 'asha', 'bhai', 'boro', 'chilo',
    'diye', 'ektu', 'gece', 'hobe', 'jabo', 'keno', 'kore',
    'lagce', 'lagche', 'nai', 'onek', 'osusto', 'hochhe',
    'hocche', 'thakbo', 'dekho', 'jani', 'mane', 'hoye',
    'kintu', 'tahole', 'dhaka', 'nsu', 'buet', 'dhanmondi',
    'mirpur', 'uttara', 'gulshan', 'banani', 'bashundhara',
    'kharap', 'valo', 'bhalo', 'kothay', 'jacchi', 'asche',
]

# Language codes that langdetect often wrongly assigns to Banglish text
UNLIKELY_LANGS = ['sq', 'et', 'lt', 'lv', 'sl', 'sk', 'hr', 'mk', 'cy', 'af']


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def detect_language(text):
    """
    Detects language of input text.
    Returns ISO 639-1 language code e.g. 'en', 'bn', 'hi', 'ar'.
    Falls back to 'en' on failure.
    """
    if not _langdetect_available:
        return 'en'
    try:
        if len(text.strip()) < 10:
            return 'en'
        return detect(text)
    except LangDetectException:
        return 'en'


def is_banglish(text, detected_lang):
    """
    Detects Banglish — Roman-script Bengali common on Bangladeshi social media.
    """
    text_lower = text.lower()

    # Rule 1 — mixed Bangla unicode + Roman characters = definitely Banglish
    bangla_chars = re.findall(r'[\u0980-\u09FF]', text)
    roman_words  = re.findall(r'[a-zA-Z]{3,}', text)
    if len(bangla_chars) > 0 and len(roman_words) > 2:
        return True

    # Rule 2 — 2+ Banglish marker words found
    banglish_hits = sum(1 for m in BANGLISH_MARKERS if m in text_lower)
    if banglish_hits >= 2:
        return True

    # Rule 3 — weird language detected (langdetect confused by Banglish)
    if detected_lang in UNLIKELY_LANGS and len(roman_words) > 3:
        return True

    # Rule 4 — detected English but contains Bangla health keywords
    bangla_kw_hits = sum(
        1 for kw in SYMPTOM_KEYWORDS['bn'] if kw in text
    )
    if detected_lang == 'en' and bangla_kw_hits > 0:
        return True

    return False


def has_health_keywords(text, lang='en'):
    """
    Checks for health-related keywords.
    Returns a boost value between 0.0 and 0.30.
    """
    text_lower = text.lower()

    universal_hits = sum(
        1 for kw in UNIVERSAL_KEYWORDS if kw in text_lower
    )
    lang_keywords = SYMPTOM_KEYWORDS.get(lang, SYMPTOM_KEYWORDS['en'])
    lang_hits = sum(1 for kw in lang_keywords if kw in text_lower)

    # Also check Bangla keywords regardless of detected language
    bangla_hits = sum(
        1 for kw in SYMPTOM_KEYWORDS['bn'] if kw in text
    )

    total = universal_hits + lang_hits + bangla_hits

    if total == 0:   return 0.0
    elif total == 1: return 0.12
    elif total == 2: return 0.22
    else:            return 0.30


def _keyword_only_score(text, lang='en'):
    """
    Fallback scoring when torch/transformers are unavailable.
    Uses only keyword matching — still quite effective for health signals.
    Returns 0-100 score.
    """
    boost = has_health_keywords(text, lang)

    # Banglish detection for extra context
    banglish = is_banglish(text, lang)

    # Base score from keyword density
    if boost >= 0.30:
        base = 55.0   # Multiple health keywords = likely outbreak signal
    elif boost >= 0.22:
        base = 42.0
    elif boost >= 0.12:
        base = 28.0
    else:
        base = 12.0   # No health keywords = low risk

    # Add keyword boost
    final = min(round(base + (boost * 100), 2), 100.0)
    return final


# ─────────────────────────────────────────────────────────────
# MAIN ENGINE CLASS
# ─────────────────────────────────────────────────────────────

class MultiLingualSymptomEngine:
    """
    Multi-lingual symptom detection engine for pandemic early warning.

    Uses two instances of XLM-RoBERTa-base as an ensemble:
      - Primary   → scores all languages
      - Secondary → ensemble partner for Bangla/Banglish

    Combined with keyword boosting for improved health signal detection.

    Falls back to keyword-only mode if torch/transformers unavailable.
    """

    def __init__(self):
        self.xlmroberta_ready  = False
        self.banglabert_ready  = False
        self.xlmroberta        = None
        self.banglabert        = None
        self.keyword_only      = False
        self.uses_finetuned    = False  # True when fine-tuned 2-class model is loaded

        print("🌍 Initializing Multi-Lingual Symptom Detection Engine...")
        print("   Supports: Bangla, Banglish, English, Hindi, Arabic,")
        print("             French, Spanish, Portuguese, Indonesian,")
        print("             Urdu, Malay, Tamil (11 languages)")
        print()

        if _transformers_available:
            self._load_xlmroberta()
            self._load_banglabert()

            if self.xlmroberta_ready:
                mode = "Fine-tuned 2-class" if self.uses_finetuned else "Base sentiment 3-class"
                print(f"\n✅ Engine ready — {mode} model active")
            else:
                print("\n⚠️  Engine ready — Limited mode")
        else:
            self.keyword_only = True
            print("\n⚠️  PyTorch/Transformers not available.")
            print("   Running in KEYWORD-ONLY mode.")
            print("   Scores will be based on health-keyword matching only.")
            print("   To enable ML models, fix your PyTorch installation:")
            print("   → pip uninstall torch")
            print("   → pip install torch --index-url https://download.pytorch.org/whl/cpu")
            print("   → Or install Visual C++ Redistributable 2019-2022")
            print()

    def _load_xlmroberta(self):
        """Primary model — fine-tuned BioGuard XLM-RoBERTa if available,
        otherwise falls back to base cardiffnlp model."""
        finetuned_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "models", "bioguard_xlm_finetuned"
        )

        # Check if fine-tuned model exists
        if os.path.isdir(finetuned_path) and \
           os.path.exists(os.path.join(finetuned_path, "config.json")):
            try:
                print("Using fine-tuned BioGuard NLP model")
                self.xlmroberta = pipeline(
                    "text-classification",
                    model=finetuned_path,
                    tokenizer=finetuned_path,
                    max_length=128,
                    truncation=True,
                    device=-1,
                )
                self.xlmroberta_ready = True
                self.uses_finetuned = True
                print("BioGuard fine-tuned model loaded!")
                return
            except Exception as e:
                print(f"Fine-tuned model failed to load: {e}")
                print("Falling back to base model...")

        # Fallback to base model
        try:
            print("Fine-tuned model not found - using base XLM-RoBERTa")
            self.xlmroberta = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                tokenizer="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                max_length=128,
                truncation=True,
                device=-1,
            )
            self.xlmroberta_ready = True
            self.uses_finetuned = False
            print("Base XLM-RoBERTa loaded!")
        except Exception as e:
            print(f"Base model also failed: {e}")
            self._load_fallback_bert()

    def _load_banglabert(self):
        """
        Secondary model — second XLM-RoBERTa instance used as
        ensemble partner for Bangla/Banglish text.
        """
        try:
            print("📥 Loading ensemble partner (Bangla/Banglish)...")
            self.banglabert = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                tokenizer="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                max_length=128,
                truncation=True,
                device=-1,
            )
            self.banglabert_ready = True
            print("✅ Ensemble partner loaded!")
        except Exception as e:
            print(f"⚠️  Ensemble partner failed: {e}")
            self.banglabert_ready = False

    def _load_fallback_bert(self):
        """Fallback to English DistilBERT if XLM-RoBERTa fails."""
        try:
            self.xlmroberta = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                max_length=128,
                truncation=True,
                device=-1,
            )
            self.xlmroberta_ready = True
            print("✅ Fallback English BERT loaded")
        except Exception as e:
            print(f"❌ All models failed to load: {e}")
            print("   Switching to keyword-only mode.")
            self.keyword_only = True

    def _score_with_model(self, model_pipeline, text):
        """
        Runs inference and maps model output to outbreak risk score 0-100.

        FINE-TUNED model (2-class: LABEL_0=not outbreak, LABEL_1=outbreak):
          LABEL_1 confidence → high risk score
          LABEL_0 confidence → low risk score

        BASE sentiment model (3-class: NEGATIVE/NEUTRAL/POSITIVE):
          NEGATIVE sentiment → higher risk (sick posts are negative)
          NEUTRAL → moderate baseline
          POSITIVE → low risk
        """
        try:
            result = model_pipeline(text[:512])[0]
            label  = result['label'].upper()
            conf   = result['score']

            # ── Fine-tuned 2-class model ──
            if self.uses_finetuned:
                if label in ['LABEL_1']:
                    # Outbreak signal detected — confidence maps to high score
                    return conf * 100
                else:
                    # Not an outbreak signal
                    return (1 - conf) * 30  # 0–30 range

            # ── Base 3-class sentiment model ──
            else:
                if label in ['NEGATIVE', 'NEG', 'LABEL_0']:
                    return conf * 100           # 0–100
                elif label in ['POSITIVE', 'POS', 'LABEL_2']:
                    return (1 - conf) * 40      # 0–40
                else:
                    return 35.0                 # Neutral baseline

        except Exception:
            return 30.0

    def analyze_text_signals(self, text):
        """
        PRIMARY METHOD — called from app.py for every post.

        Returns a risk score between 0 and 100.
        Higher = stronger outbreak signal detected.

        Pipeline:
          1. Detect language
          2. Detect Banglish
          3. Route to correct model(s) OR keyword fallback
          4. Apply keyword boost
          5. Clamp and return final score
        """
        if not text or len(text.strip()) < 3:
            return 0.0

        # Step 1 — Language detection
        lang     = detect_language(text)
        banglish = is_banglish(text, lang)

        # Step 2 — Keyword boost (always computed)
        boost = has_health_keywords(text, lang)

        # ── KEYWORD-ONLY MODE (torch broken) ──
        if self.keyword_only:
            return _keyword_only_score(text, lang)

        # Step 3 — Model scoring
        if banglish:
            # Ensemble: average both model scores
            s1 = self._score_with_model(self.xlmroberta, text) \
                 if self.xlmroberta_ready else 30.0
            s2 = self._score_with_model(self.banglabert, text) \
                 if self.banglabert_ready else 30.0
            base_score = (s1 + s2) / 2

        elif lang == 'bn':
            # Pure Bangla — use primary model
            base_score = self._score_with_model(self.xlmroberta, text) \
                         if self.xlmroberta_ready else 30.0

        else:
            # English or any other of 104 languages
            base_score = self._score_with_model(self.xlmroberta, text) \
                         if self.xlmroberta_ready else 30.0

        # Step 4 — Apply keyword boost
        final_score = min(round(base_score + (boost * 100), 2), 100.0)

        return final_score

    def analyze_batch(self, posts):
        """
        Scores a list of post documents from MongoDB.
        Returns list of dicts with score and language metadata.
        """
        results = []
        for post in posts:
            text = post.get('text', '')
            lang = detect_language(text)
            results.append({
                'post':     post,
                'score':    self.analyze_text_signals(text),
                'language': lang,
                'banglish': is_banglish(text, lang),
            })
        return results

    def get_engine_status(self):
        """Returns engine status for /api/engine-status endpoint."""
        models = []
        if self.xlmroberta_ready:
            if self.uses_finetuned:
                models.append("BioGuard XLM-RoBERTa (fine-tuned, 2-class) — Primary")
            else:
                models.append("XLM-RoBERTa-base (sentiment, 104 langs) — Primary")
        if self.banglabert_ready:
            models.append("XLM-RoBERTa-base (104 langs) — Ensemble Partner")
        if self.keyword_only:
            models.append("Keyword-Only Fallback (no ML)")

        return {
            "xlmroberta_active":   self.xlmroberta_ready,
            "banglabert_active":   self.banglabert_ready,
            "keyword_only_mode":   self.keyword_only,
            "uses_finetuned":      self.uses_finetuned,
            "languages_supported": 11,  # en, bn, hi, ar, pt, fr, es, id, ur, ms, ta
            "models_active":       models,
            "mode": (
                "KEYWORD-ONLY (torch unavailable)"
                if self.keyword_only else
                "Fine-tuned BioGuard Model"
                if self.uses_finetuned else
                "Multi-Lingual Ensemble"
                if self.xlmroberta_ready and self.banglabert_ready
                else "Single Model"
            ),
        }


# ─────────────────────────────────────────────
# Single global instance — imported by app.py
# ─────────────────────────────────────────────
engine = MultiLingualSymptomEngine()


# ─────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("TESTING MULTI-LINGUAL SYMPTOM DETECTION ENGINE")
    print("=" * 65)

    test_posts = [
        ("My whole family has fever and cough",              "English  HIGH"),
        ("Beautiful day in Dhaka, loving the weather",       "English  LOW"),
        ("জ্বর আর কাশি থামছে না, ডাক্তারের কাছে যাব",      "Bangla   HIGH"),
        ("আজকের আবহাওয়া অনেক সুন্দর",                       "Bangla   LOW"),
        ("Amar onek fever hochhe, hospital jabo",            "Banglish HIGH"),
        ("NSU library te study kortesi",                     "Banglish LOW"),
        ("Amar বমি hocche onek, doctor lagbe",               "Banglish HIGH"),
        ("मुझे बुखार और खांसी है, डॉक्टर के पास जाना होगा", "Hindi    HIGH"),
        ("أعاني من حمى شديدة وسعال مستمر",                  "Arabic   HIGH"),
        ("J'ai de la fièvre et je tousse beaucoup",         "French   HIGH"),
        ("Estou com febre alta e tosse, vou ao hospital",   "Portug   HIGH"),
        ("Tengo fiebre y tos, necesito ir al médico",       "Spanish  HIGH"),
        ("Saya demam tinggi dan batuk parah",               "Indones  HIGH"),
        ("Just had a great lunch at Bashundhara City",      "English  LOW"),
    ]

    print(f"\n{'Text':<48} {'Expected':<14} {'Lang':<6} {'Score':>6} {'Result'}")
    print("-" * 90)

    correct = 0
    total   = len(test_posts)

    for text, expected in test_posts:
        score = engine.analyze_text_signals(text)
        lang  = detect_language(text)

        if score > 65:
            result = "HIGH"
        elif score > 35:
            result = "MED"
        else:
            result = "LOW"

        expected_level = "HIGH" if "HIGH" in expected else "LOW"
        actual_level   = "HIGH" if score > 55 else "LOW"
        correct_mark   = "✓" if expected_level == actual_level else "✗"
        if expected_level == actual_level:
            correct += 1

        print(
            f"{text[:47]:<48} {expected:<14} "
            f"{lang:<6} {score:>6.1f} {result} {correct_mark}"
        )

    accuracy = (correct / total) * 100
    print(f"\n{'=' * 90}")
    print(f"Accuracy on test set: {correct}/{total} = {accuracy:.1f}%")

    print("\nENGINE STATUS:")
    for key, val in engine.get_engine_status().items():
        print(f"  {key}: {val}")
    print("=" * 90)