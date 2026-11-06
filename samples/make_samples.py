"""Generate synthetic change orders (inputs/) and their ground truth (expected/).

Each sample is defined once as data; the document is rendered from it, so the expected JSON is exact.
Run: python samples/make_samples.py
"""

import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

ROOT = Path(__file__).parent
INPUTS, EXPECTED = ROOT / "inputs", ROOT / "expected"

CSS = "body{font-family:sans-serif;font-size:10pt} table{border-collapse:collapse;width:100%} td,th{border:1px solid #333;padding:3px}"


def money(v: float) -> str:
    return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"


def rows(items) -> str:
    return "".join(
        f"<tr><td>{i['item']}</td><td>{i['qty']:g}</td><td>{i['unit']}</td><td>{money(i['unit_cost'])}</td><td>{money(i['total'])}</td></tr>"
        for i in items
    )


def html_pdf(html: str, path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_htmlbox(pymupdf.Rect(40, 40, 572, 752), html, css=CSS)
    doc.save(path)


def scan(pdf_path: Path, out: Path) -> None:
    """Fake a scan: render at low DPI, rotate a little, add noise and blur, save as an image-only PDF."""
    pix = pymupdf.open(pdf_path)[0].get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    img = img.rotate(0.8, expand=True, fillcolor=255, resample=Image.BICUBIC)
    noise = Image.effect_noise(img.size, 40)
    img = Image.blend(img, noise, 0.12).filter(ImageFilter.GaussianBlur(0.6))
    img.save(out, "PDF", resolution=150)


# --------------------------------------------------------------------------- samples

S1 = dict(
    change_order_number="CO-014", project_name="Riverside Clinic Phase 2", contractor="ABC Builders Ltd.",
    owner="Riverside Health Authority", date_issued="2026-03-12",
    description="Add two windows on east wall of exam room wing", reason="Owner request for additional natural light",
    reason_category="owner_request", cost_change=4250.00, currency="USD", original_contract_sum=1250000.00,
    contract_sum_before=1262400.00, revised_contract_sum=1266650.00, schedule_impact_days=3,
    approval_status="pending", approved_by=None, date_approved=None,
    line_items=[
        dict(item="Window unit 36x48", qty=2, unit="EA", unit_cost=1200.00, total=2400.00),
        dict(item="Framing and header labor", qty=16, unit="HR", unit_cost=85.00, total=1360.00),
        dict(item="Trim and finish", qty=1, unit="LS", unit_cost=490.00, total=490.00),
    ],
)

S2 = dict(
    change_order_number="7", project_name="Maple Street Library Renovation", contractor="Northline Construction Inc.",
    owner="City of Maple Grove", date_issued="2025-10-03",
    description="Substitute specified Armstrong acoustic ceiling tile with USG Mars tile",
    reason="Specified tile discontinued by manufacturer", reason_category="material_substitution",
    cost_change=-240.00, currency="USD", original_contract_sum=842500.00, contract_sum_before=851300.00,
    revised_contract_sum=851060.00, schedule_impact_days=0, approval_status="approved",
    approved_by="Dana Whitfield", date_approved="2025-10-09",
    line_items=[
        dict(item="USG Mars 2x2 ceiling tile", qty=1200, unit="SF", unit_cost=3.10, total=3720.00),
        dict(item="Restocking fee", qty=1, unit="LS", unit_cost=180.00, total=180.00),
        dict(item="Credit: specified Armstrong tile", qty=1200, unit="SF", unit_cost=-3.45, total=-4140.00),
    ],
)

S3 = dict(
    change_order_number="3", project_name="Harbor View Apartments", contractor="Summit Ridge Contractors",
    owner="Harbor View Holdings LLC", date_issued="2025-10-21",
    description="Reroute around abandoned 6 inch water main found during foundation excavation",
    reason="Abandoned water main discovered during excavation", reason_category="unforeseen_condition",
    cost_change=5840.00, currency="USD", original_contract_sum=None, contract_sum_before=None,
    revised_contract_sum=None, schedule_impact_days=4, approval_status="pending", approved_by=None, date_approved=None,
    line_items=[
        dict(item="Excavation and haul-off", qty=18, unit="HR", unit_cost=145.00, total=2610.00),
        dict(item="6 inch DIP pipe", qty=40, unit="LF", unit_cost=62.00, total=2480.00),
        dict(item="Plug and cap existing main", qty=2, unit="EA", unit_cost=375.00, total=750.00),
    ],
)

S4 = dict(  # missing CO number / date, wrong line math, line items don't sum to the stated total
    change_order_number=None, project_name="Oakwood Elementary Gym Floor", contractor="Precision Flooring Co.",
    owner=None, date_issued=None, description="Replace water-damaged gym floor section",
    reason=None, reason_category=None, cost_change=19500.00, currency="USD", original_contract_sum=None,
    contract_sum_before=None, revised_contract_sum=None, schedule_impact_days=None,
    approval_status=[None, "pending"],  # blank "Signed: ____" line: either reading is fair
    approved_by=None, date_approved=None,
    line_items=[
        dict(item="Maple floor boards", qty=2000, unit="SF", unit_cost=8.50, total=17500.00),
        dict(item="Moisture barrier", qty=2000, unit="SF", unit_cost=1.25, total=2500.00),
    ],
)

S5 = dict(
    change_order_number="2", project_name="Westgate Fire Station No. 4", contractor="Ironclad Mechanical LLC",
    owner="Westgate County", date_issued="2026-01-27",
    description="Upgrade apparatus bay sprinkler system", reason="Updated fire code (NFPA 13 revision adopted by the county)",
    reason_category="code_compliance", cost_change=12480.00, currency="USD", original_contract_sum=3400000.00,
    contract_sum_before=3415200.00, revised_contract_sum=3427680.00, schedule_impact_days=7,
    approval_status="approved", approved_by="Maria Alvarez", date_approved="2026-02-02",
    line_items=None,  # a single lump sum; one item or none are both acceptable, so not scored
)


def write_s1():
    s = S1
    html = f"""<h2>CHANGE ORDER</h2>
<table><tr><td><b>Change Order No.</b></td><td>{s['change_order_number']}</td><td><b>Date</b></td><td>03/12/2026</td></tr>
<tr><td><b>Project</b></td><td>{s['project_name']}</td><td><b>Owner</b></td><td>{s['owner']}</td></tr>
<tr><td><b>Contractor</b></td><td>{s['contractor']}</td><td><b>Status</b></td><td>Pending owner approval</td></tr></table>
<p><b>Description of change:</b> {s['description']}.<br><b>Reason:</b> {s['reason']}.</p>
<table><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Unit Cost</th><th>Total</th></tr>{rows(s['line_items'])}
<tr><td colspan=4><b>Total this Change Order</b></td><td><b>{money(s['cost_change'])}</b></td></tr></table>
<p>Original Contract Sum: {money(s['original_contract_sum'])}<br>
Contract Sum prior to this Change Order: {money(s['contract_sum_before'])}<br>
Revised Contract Sum: {money(s['revised_contract_sum'])}<br>
Contract Time will be increased by {s['schedule_impact_days']} calendar days.</p>
<p>Owner signature: ____________________ Date: __________</p>"""
    html_pdf(html, INPUTS / "s1_digital_table.pdf")


def write_s2():
    s = S2
    html = f"""<h2>Northline Construction Inc. &mdash; CHANGE ORDER #{s['change_order_number']}</h2>
<p>Date issued: October 3, 2025<br>Project: {s['project_name']}<br>Owner: {s['owner']}</p>
<p><b>Change:</b> {s['description']}.<br><b>Reason:</b> {s['reason']}.</p>
<table><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Unit Cost</th><th>Total</th></tr>{rows(s['line_items'])}</table>
<p>Net decrease this Change Order: {money(abs(s['cost_change']))}<br>
Original Contract Sum: {money(s['original_contract_sum'])}<br>
Contract Sum prior to this Change Order: {money(s['contract_sum_before'])}<br>
New Contract Sum: {money(s['revised_contract_sum'])}<br>
Contract Time: unchanged.</p>
<p>APPROVED for Owner: {s['approved_by']}, Facilities Director &nbsp;&nbsp; Date: 10/09/2025</p>"""
    tmp = INPUTS / "_s2_clean.pdf"
    html_pdf(html, tmp)
    scan(tmp, INPUTS / "s2_scanned.pdf")
    tmp.unlink()


def write_s3():
    s = S3
    text = f"""From: Rick Moreno <rmoreno@summitridge.example>
To: Owner's Rep <pm@harborviewholdings.example>
Date: Tue, 21 Oct 2025 09:14:02 -0700
Subject: CO 3 - Harbor View Apartments - abandoned water line

Hi Jen,

While excavating for the east foundation wall on Oct 14 we hit an abandoned 6" water main
that isn't on any of the survey drawings. We need to cut, plug and reroute around it before
we can pour. Pricing below:

  - Excavation and haul-off: 18 hrs @ $145/hr = $2,610.00
  - 6 inch DIP pipe: 40 LF @ $62.00 = $2,480.00
  - Plug and cap existing main: 2 EA @ $375.00 = $750.00

  Total CO 3: $5,840.00

We'll need 4 extra working days added to the schedule. Please approve so we can keep moving.

Thanks,
Rick Moreno
Project Manager, {s['contractor']}
(on behalf of the GC for {s['owner']})
"""
    (INPUTS / "s3_email.txt").write_text(text, encoding="utf-8")


def write_s4():
    s = S4
    text = f"""CHANGE ORDER

Project: {s['project_name']}
Contractor: {s['contractor']}

Work: {s['description']}.

  Maple floor boards      2,000 SF  x $8.50   = $17,500.00
  Moisture barrier        2,000 SF  x $1.25   =  $2,500.00

  TOTAL CHANGE: $19,500.00

Signed: ______________
"""
    (INPUTS / "s4_missing_and_bad_math.txt").write_text(text, encoding="utf-8")


def write_s5():
    s = S5
    html = f"""<p style="text-align:right">January 27, 2026</p>
<p><b>MEMORANDUM</b><br>TO: Westgate County Board of Commissioners<br>FROM: Capital Projects Office<br>
RE: Change Order No. 2 &mdash; {s['project_name']}</p>
<p>Due to the updated fire code (NFPA 13 revision adopted by the county), the sprinkler system in the
apparatus bay must be upgraded to a higher density design. The contractor, {s['contractor']}, has priced the
work at {money(s['cost_change'])} lump sum and requests an extension of {s['schedule_impact_days']} calendar days.</p>
<p>The original contract sum was {money(s['original_contract_sum'])}. With prior change orders the contract stands at
{money(s['contract_sum_before'])}; this change order brings it to {money(s['revised_contract_sum'])}.</p>
<p>This change order was approved by Fire Chief {s['approved_by']} on February 2, 2026.</p>"""
    html_pdf(html, INPUTS / "s5_narrative_memo.pdf")


def expected(s: dict) -> dict:
    out = {k: v for k, v in s.items() if k != "line_items"}
    if s["line_items"] is not None:
        out["line_items_totals"] = [i["total"] for i in s["line_items"]]
    return out


if __name__ == "__main__":
    INPUTS.mkdir(exist_ok=True)
    EXPECTED.mkdir(exist_ok=True)
    for name, s, fn in [("s1_digital_table", S1, write_s1), ("s2_scanned", S2, write_s2), ("s3_email", S3, write_s3),
                        ("s4_missing_and_bad_math", S4, write_s4), ("s5_narrative_memo", S5, write_s5)]:
        fn()
        (EXPECTED / f"{name}.json").write_text(json.dumps(expected(s), indent=2), encoding="utf-8")
        print("wrote", name)
