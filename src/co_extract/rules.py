"""Regex extraction for well-defined fields. Used to cross-check the LLM and as a no-API-key fallback."""

import re
from datetime import date

from dateutil import parser as dateparser

DATE = (
    r"(\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|[A-Z][a-z]{2,8}\.?\s*\d{1,2},?\s*\d{4})"
)
NUMBER_WORDS = {"zero": 0, "no": 0}


def L(phrase: str) -> str:
    """Label pattern that tolerates missing/extra whitespace ('ChangeOrderNumber' or 'Change  Order Number')."""
    return r"\s*".join(re.escape(w) for w in phrase.split())


def _first(patterns: list[str], text: str) -> re.Match | None:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m
    return None


def _money(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def change_order_number(text: str) -> str | None:
    m = _first(
        [
            L("change order") + r"\s*(?:no\.?|number|#)\s*[:.]?\s*:?\s*([A-Z0-9][\w-]*)",
            r"\bC\.?O\.?\s*(?:#|no\.?)?\s*[:-]?\s*(\d[\w-]*)",
        ],
        text,
    )
    return m.group(1) if m else None


def date_issued(text: str) -> date | None:
    m = _first(
        [lbl + r"\s*:?\s*" + DATE for lbl in (L("date of issuance"), L("date issued"), L("issue date"))],
        text,
    )
    if not m:
        return None
    try:
        return dateparser.parse(m.group(1).replace("Sept", "Sep")).date()
    except (ValueError, OverflowError):
        return None


def cost_change(text: str) -> float | None:
    label = (
        r"((?:increase|decrease|deduct|credit)[^$\n]{0,40}?" + L("this change order")
        + r"|" + L("contract sum will be") + r"\s*(?:increased|decreased)\s*" + L("by this change order in the amount of")
        + r"|" + L("total amount of change order")
        + r"|" + L("change order in the") + r"\s*(?:increased|decreased)\s*" + L("amount of") + r")"
    )
    m = re.search(label + r"[^$]{0,120}?\$\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    value = _money(m.group(2))
    if value is not None and re.search(r"decrease|deduct|credit", m.group(1), re.IGNORECASE):
        value = -value
    return value


def original_contract_sum(text: str) -> float | None:
    m = _first([L("original contract") + r"\s*(?:sum|price|amount)[^$]{0,120}?\$\s*([\d,]+(?:\.\d+)?)"], text)
    return _money(m.group(1)) if m else None


def contract_sum_before(text: str) -> float | None:
    m = _first([r"(?:sum|price)\s*" + L("prior to this change order") + r"[^$]{0,120}?\$\s*([\d,]+(?:\.\d+)?)"], text)
    return _money(m.group(1)) if m else None


def revised_contract_sum(text: str) -> float | None:
    m = _first(
        [
            L("new contract sum including this change order") + r"[^$]{0,40}?\$\s*([\d,]+(?:\.\d+)?)",
            L("contract price incorporating this change order") + r"[^$]{0,120}?\$\s*([\d,]+(?:\.\d+)?)",
            L("revised contract") + r"\s*(?:sum|price|amount|total)[^$]{0,40}?\$\s*([\d,]+(?:\.\d+)?)",
        ],
        text,
    )
    return _money(m.group(1)) if m else None


def schedule_impact_days(text: str) -> int | None:
    m = _first(
        [
            L("contract time will be") + r"\s*(increased|decreased)\s*by\s*(\w+)?\s*\(?(\d+)?\)?\s*days",
            r"(add(?:s|ed)?|increase[sd]?\s*by|extension\s*of|addition\s*of)\s*()(\d+)\s*(?:calendar|working)?\s*days",
        ],
        text,
    )
    if m:
        n = m.group(3) or NUMBER_WORDS.get((m.group(2) or "").lower())
        if n is None:
            return None
        return -int(n) if m.group(1).lower().startswith("decrease") else int(n)
    if re.search(L("contract time") + r"[^.\n]{0,40}(unchanged|no change)", text, re.IGNORECASE):
        return 0
    return None


def currency(text: str) -> str | None:
    m = re.search(r"\b(USD|CAD|EUR|GBP|AUD)\b", text)
    if m:
        return m.group(1)
    return "USD" if "$" in text else None


RULES = {
    "change_order_number": change_order_number,
    "date_issued": date_issued,
    "cost_change": cost_change,
    "currency": currency,
    "original_contract_sum": original_contract_sum,
    "contract_sum_before": contract_sum_before,
    "revised_contract_sum": revised_contract_sum,
    "schedule_impact_days": schedule_impact_days,
}


def extract(text: str) -> dict:
    return {name: fn(text) for name, fn in RULES.items()}
