"""Per-field confidence: a weighted mean of independent signals, times a penalty for failed checks.

Signals (each 0..1, only included when it applies):
  agreement  fraction of LLM passes that produced the chosen value
  grounding  does the value actually appear in the source text (word overlap for free-text summaries;
             weak keyword evidence for interpretive fields, which can't be verified from text alone)
  rule       does the regex extractor agree (only when the regex found something)
  ocr        Tesseract confidence of the matching words (scanned input only)
"""

import re
from datetime import date

from rapidfuzz import fuzz

WEIGHTS = {"agreement": 0.35, "grounding": 0.35, "rule": 0.15, "ocr": 0.15}
FAILED_CHECK_PENALTY = 0.5
RULES_ONLY_FACTOR = 0.8  # no second opinion without the LLM

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

KEYWORDS = {
    "approval_status": {
        "approved": ["approved", "accepted", "authorized", "signed"],
        "pending": ["pending", "recommend", "request", "consideration", "not valid until", "proposed"],
        "rejected": ["reject", "denied", "declined"],
    },
    "reason_category": {
        "owner_request": ["owner request", "client request", "requested by owner", "owner"],
        "design_change": ["design", "revised drawing", "rfi", "architect", "engineer"],
        "unforeseen_condition": ["unforeseen", "discovered", "existing", "site condition", "uncover"],
        "material_substitution": ["substitut", "unavailable", "alternate", "lead time"],
        "code_compliance": ["code", "inspector", "compliance", "regulation", "fire marshal"],
    },
}


def norm(v) -> str:
    """Comparison key: case/space/punctuation-insensitive, numbers rounded, leading zeros on IDs dropped."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"{float(v):.2f}"
    if hasattr(v, "value"):  # enums
        v = v.value
    s = re.sub(r"[^a-z0-9]", "", str(v).lower())
    s = re.sub(r"^(changeorder|co)(no|number)?(?=\d)", "", s)  # "CO 3" / "Change Order No. 3" -> "3"
    return s.lstrip("0") or s


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _number_forms(v: float) -> list[str]:
    v = abs(v)
    forms = [f"{v:,.2f}", f"{v:.2f}"]
    if v == int(v):
        forms += [f"{int(v):,}", str(int(v))]
    return forms


def _date_forms(d: date) -> list[str]:
    m, dd, y = d.month, d.day, d.year
    name = MONTHS[m - 1]
    forms = [d.isoformat(), f"{m}/{dd}/{y}", f"{m:02}/{dd:02}/{y}", f"{m}/{dd}/{y % 100:02}",
             f"{name}{dd},{y}", f"{name[:3]}.{dd},{y}", f"{name[:3]}{dd},{y}", f"{name[:4]}.{dd},{y}",
             f"{dd}{name}{y}", f"{dd}{name[:3]}{y}"]
    return [f.replace(" ", "") for f in forms]


FREE_TEXT = {"description", "reason"}


def grounding(field: str, value, text: str) -> float:
    """1.0 if the value is literally in the text, partial credit for fuzzy matches, low if absent."""
    flat = squash(text)
    if field in KEYWORDS:
        # interpretive: keywords are weak evidence (every blank form says "Approved by"), so cap at 0.5
        words = KEYWORDS[field].get(getattr(value, "value", value), [])
        return 0.5 if any(w.replace(" ", "") in flat for w in words) else 0.2
    if field in FREE_TEXT:
        # summaries are paraphrased: score the share of their content words found in the source
        words = set(re.findall(r"[a-z0-9]{4,}", str(value).lower()))
        source = set(re.findall(r"[a-z0-9]{4,}", text.lower()))
        return round(len(words & source) / len(words), 2) if words else 0.0
    if field == "currency":
        return 1.0 if value.lower() in flat or (value == "USD" and "$" in text) else 0.0
    if isinstance(value, date):
        return 1.0 if any(f in flat for f in _date_forms(value)) else 0.0
    if isinstance(value, (int, float)):
        if field == "schedule_impact_days":
            return 1.0 if re.search(rf"(?<![\d.,]){abs(int(value))}(?![\d.,]\d)", text) or value == 0 else 0.0
        return 1.0 if any(f in flat for f in _number_forms(value)) else 0.0
    s = str(value)
    if squash(s) in flat:
        return 1.0
    # partial_ratio gives ~0.5 even to unrelated strings, so rescale 0.6..1.0 -> 0..1
    ratio = fuzz.partial_ratio(s.lower(), text.lower()) / 100
    return round(max(0.0, (ratio - 0.6) / 0.4), 2)


def ocr_signal(value, ocr_words: dict[str, float]) -> float | None:
    """Mean OCR confidence of the value's tokens that came from OCR; None if none did."""
    if not ocr_words or value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        tokens = _number_forms(value)[:1] + _number_forms(value)[2:3]
    else:
        tokens = re.findall(r"[\w.$/-]+", str(getattr(value, "value", value)).lower())
    confs = [ocr_words[t.strip(".")] for t in tokens if t.strip(".") in ocr_words]
    return round(sum(confs) / len(confs), 2) if confs else None


def combine(signals: dict[str, float], failed_check: bool, rules_only: bool) -> float:
    present = {k: v for k, v in signals.items() if k in WEIGHTS}
    if not present:
        return 0.0
    score = sum(WEIGHTS[k] * v for k, v in present.items()) / sum(WEIGHTS[k] for k in present)
    if failed_check:
        score *= FAILED_CHECK_PENALTY
    if rules_only:
        score *= RULES_ONLY_FACTOR
    return round(min(max(score, 0.0), 1.0), 2)
