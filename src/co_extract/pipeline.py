"""ingest -> LLM passes + regex -> majority vote -> validate -> score."""

import os
from pathlib import Path

from dotenv import load_dotenv

from . import confidence as conf
from . import ingest, llm, rules, validate
from .schema import SCALAR_FIELDS, Check, Extraction, Result

load_dotenv()

TEMPERATURES = [0.0, 0.7, 0.7]  # pass 1 deterministic, passes 2-3 sampled for the agreement signal
UNPENALIZED_CHECKS = {"not_invented", "required_present"}  # already reflected in grounding / nothing to blame


def run_path(path: str | Path, passes: int | None = None) -> Result:
    return run(ingest.load(path), passes)


def run_text(text: str, passes: int | None = None) -> Result:
    return run(ingest.from_text(text), passes)


def run(doc: ingest.Document, passes: int | None = None) -> Result:
    passes = passes or int(os.getenv("LLM_PASSES", len(TEMPERATURES)))
    rule_vals = rules.extract(doc.text)

    extractions: list[Extraction] = []
    if llm.available():
        for i in range(passes):
            x = llm.extract(doc.text, TEMPERATURES[min(i, len(TEMPERATURES) - 1)])
            if x is not None:
                extractions.append(x)
    use_llm = bool(extractions)

    # 1. choose a value per field
    values, agreement = {}, {}
    for f in SCALAR_FIELDS:
        if use_llm:
            values[f], agreement[f] = _vote([getattr(x, f) for x in extractions])
        else:
            values[f] = rule_vals.get(f)
    items, item_agreement = _vote_line_items(extractions) if use_llm else ([], [])
    final = Extraction(**values, line_items=items)

    # 2. validate
    checks = validate.run(final)
    for f in SCALAR_FIELDS:
        v = getattr(final, f)
        if v is not None and f not in conf.KEYWORDS and conf.grounding(f, v, doc.text) < 0.5:
            checks.append(Check(check="not_invented", fields=[f], passed=False,
                                message=f"{f}={v!r} not found in source text"))
    failed = {fld for c in checks if not c.passed and c.check not in UNPENALIZED_CHECKS for fld in c.fields}

    # 3. score
    out: dict = {}
    for f in SCALAR_FIELDS:
        v, rule_v = getattr(final, f), rule_vals.get(f)
        signals: dict[str, float] = {}
        if use_llm:
            signals["agreement"] = round(agreement[f], 2)
        if v is None:
            # confidence that the field is genuinely absent
            score = agreement[f] if use_llm else 0.5
            if rule_v is not None:
                signals["rule"] = 0.0
                score *= 0.5
            out[f] = {"value": None, "confidence": round(score, 2), "signals": signals}
            continue
        signals["grounding"] = conf.grounding(f, v, doc.text)
        if use_llm and rule_v is not None:
            signals["rule"] = 1.0 if conf.norm(rule_v) == conf.norm(v) else 0.0
        if doc.ocr_text and conf.grounding(f, v, doc.ocr_text) >= 0.5:  # value came from a scanned page
            if (o := conf.ocr_signal(v, doc.ocr_words)) is not None:
                signals["ocr"] = o
        out[f] = {"value": v, "signals": signals,
                  "confidence": conf.combine(signals, f in failed, rules_only=not use_llm)}

    out["line_items"] = []
    for i, li in enumerate(final.line_items):
        g = [conf.grounding("item", li.item, doc.text)] if li.item else []
        g += [conf.grounding("total", li.total, doc.text)] if li.total is not None else []
        signals = {"agreement": round(item_agreement[i], 2), "grounding": round(sum(g) / len(g), 2) if g else 0.0}
        bad = f"line_items[{i}]" in failed or "line_items" in failed
        out["line_items"].append({**li.model_dump(), "signals": signals,
                                  "confidence": conf.combine(signals, bad, rules_only=False)})

    out["validation"] = checks
    out["meta"] = {
        "source_type": doc.source_type,
        "pages": doc.pages,
        "mode": "llm" if use_llm else "rules_only",
        "model": llm.model_name() if use_llm else None,
        "passes": len(extractions),
        "ocr_mean_confidence": round(sum(doc.ocr_words.values()) / len(doc.ocr_words), 2) if doc.ocr_words else None,
    }
    return Result.model_validate(out)


def _vote(values: list):
    """Majority value by normalized key; ties go to the earliest (temperature 0) pass."""
    keys = [conf.norm(v) for v in values]
    best = max(dict.fromkeys(keys), key=keys.count)
    return values[keys.index(best)], keys.count(best) / len(keys)


def _vote_line_items(extractions: list[Extraction]):
    """Take the list from the pass with the most common item count; score each item by how many passes contain it."""
    counts = [len(x.line_items) for x in extractions]
    base = extractions[counts.index(max(set(counts), key=counts.count))].line_items

    def key(li):
        return conf.norm(li.total) if li.total is not None else conf.norm(li.item)

    agreement = [sum(any(key(o) == key(li) for o in x.line_items) for x in extractions) / len(extractions)
                 for li in base]
    return base, agreement
