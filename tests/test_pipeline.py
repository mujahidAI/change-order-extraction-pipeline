"""Offline tests: no network. The LLM is replaced by canned extractions."""

from datetime import date
from pathlib import Path

import pytest

from co_extract import confidence, ingest, llm, pipeline, rules, validate
from co_extract.schema import Extraction, LineItem

SAMPLES = Path(__file__).parent.parent / "samples"

TEXT = """CHANGE ORDER No. CO-014
Date Issued: 03/12/2026
Project: Riverside Clinic Phase 2      Contractor: ABC Builders Ltd.
Add two windows on east wall. Reason: owner request.
  Window unit 36x48   2 EA @ $1,200.00 = $2,400.00
  Framing labor      16 HR @ $85.00    = $1,360.00
Increase this Change Order: $3,760.00
Contract Sum prior to this Change Order: $100,000.00
New Contract Sum including this Change Order will be $103,760.00
The Contract Time will be increased by three (3) days.
"""

GOOD = Extraction(
    change_order_number="CO-014", project_name="Riverside Clinic Phase 2", contractor="ABC Builders Ltd.",
    date_issued=date(2026, 3, 12), cost_change=3760.0, currency="USD", contract_sum_before=100000.0,
    revised_contract_sum=103760.0, schedule_impact_days=3, reason_category="owner_request",
    line_items=[LineItem(item="Window unit 36x48", qty=2, unit="EA", unit_cost=1200, total=2400),
                LineItem(item="Framing labor", qty=16, unit="HR", unit_cost=85, total=1360)],
)


# ------------------------------------------------------------------ rules

def test_rules_extract_well_defined_fields():
    r = rules.extract(TEXT)
    assert r["change_order_number"] == "CO-014"
    assert r["date_issued"] == date(2026, 3, 12)
    assert r["cost_change"] == 3760.0
    assert r["contract_sum_before"] == 100000.0
    assert r["revised_contract_sum"] == 103760.0
    assert r["schedule_impact_days"] == 3


def test_rules_handle_decrease_and_missing_spaces():
    assert rules.cost_change("Decrease of this Change Order:\n\n$14,000.00") == -14000.0
    squashed = "TheContractSumwillbeincreasedbythisChangeOrderintheamountof$ 1,021,837.00"
    assert rules.cost_change(squashed) == 1021837.0
    assert rules.schedule_impact_days("The Contract Time will be increased by Zero (0) days.") == 0


# ------------------------------------------------------------------ validation

def test_validation_passes_on_consistent_data():
    assert all(c.passed for c in validate.run(GOOD))


def test_validation_catches_bad_math_and_dates():
    bad = GOOD.model_copy(update={
        "line_items": [LineItem(item="x", qty=2, unit_cost=100, total=250)],
        "revised_contract_sum": 999.0,
        "date_issued": date(1970, 1, 1),
    })
    failed = {c.check for c in validate.run(bad) if not c.passed}
    assert {"line_item_math", "line_items_sum", "contract_sum_math", "date_plausible"} <= failed


# ------------------------------------------------------------------ confidence

def test_grounding():
    assert confidence.grounding("cost_change", 3760.0, TEXT) == 1.0
    assert confidence.grounding("cost_change", 9999.0, TEXT) == 0.0
    assert confidence.grounding("date_issued", date(2026, 3, 12), TEXT) == 1.0
    assert confidence.grounding("contractor", "ABC Builders Ltd.", TEXT) == 1.0
    assert confidence.grounding("contractor", "Totally Different Corp", TEXT) < 0.7


def test_combine_penalizes_failed_checks():
    s = {"agreement": 1.0, "grounding": 1.0}
    assert confidence.combine(s, failed_check=False, rules_only=False) == 1.0
    assert confidence.combine(s, failed_check=True, rules_only=False) == 0.5


# ------------------------------------------------------------------ pipeline (LLM mocked)

@pytest.fixture
def fake_llm(monkeypatch):
    def install(passes: list[Extraction]):
        it = iter(passes)
        monkeypatch.setattr(llm, "available", lambda: True)
        monkeypatch.setattr(llm, "extract", lambda text, temperature=0.0: next(it))
    return install


def test_agreeing_grounded_fields_score_high(fake_llm):
    fake_llm([GOOD, GOOD, GOOD])
    r = pipeline.run_text(TEXT)
    assert r.meta["mode"] == "llm"
    assert r.cost_change.value == 3760.0 and r.cost_change.confidence >= 0.9
    assert r.owner.value is None and r.owner.confidence == 1.0  # all passes agree it's absent
    assert all(li.confidence >= 0.9 for li in r.line_items)
    assert all(c.passed for c in r.validation)


def test_hallucinated_or_disputed_fields_score_low(fake_llm):
    invented = GOOD.model_copy(update={"contractor": "Imaginary Builders Inc."})
    other = GOOD.model_copy(update={"schedule_impact_days": 30})
    fake_llm([invented, invented, other])
    r = pipeline.run_text(TEXT)
    assert r.contractor.confidence < 0.7
    assert any(c.check == "not_invented" and not c.passed for c in r.validation)


def test_rules_only_fallback(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    r = pipeline.run_text(TEXT)
    assert r.meta["mode"] == "rules_only"
    assert r.change_order_number.value == "CO-014"
    assert r.change_order_number.confidence <= confidence.RULES_ONLY_FACTOR


# ------------------------------------------------------------------ ingest

def test_ingest_text_and_digital_pdf():
    doc = ingest.load(SAMPLES / "inputs" / "s3_email.txt")
    assert doc.source_type == "text" and "$5,840.00" in doc.text
    doc = ingest.load(SAMPLES / "inputs" / "s1_digital_table.pdf")
    assert doc.source_type == "pdf_digital" and "Riverside Clinic Phase 2" in doc.text
