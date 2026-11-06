"""Business-rule checks. Each check reports pass/fail; nothing raises."""

from datetime import date, timedelta

from .schema import Check, Extraction

MIN_DATE = date(1990, 1, 1)


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 0.01 + 1e-4 * abs(b)


def run(x: Extraction, today: date | None = None) -> list[Check]:
    today = today or date.today()
    checks: list[Check] = []

    def add(name, fields, passed, message):
        checks.append(Check(check=name, fields=fields, passed=passed, message=message))

    for f in ("date_issued", "date_approved"):
        d = getattr(x, f)
        if d is not None:
            ok = MIN_DATE <= d <= today + timedelta(days=730)
            add("date_plausible", [f], ok, f"{f}={d}" + ("" if ok else " is outside 1990..today+2y"))

    if x.date_issued and x.date_approved:
        ok = x.date_approved >= x.date_issued
        add("date_order", ["date_issued", "date_approved"], ok, f"approved {x.date_approved} vs issued {x.date_issued}")

    for i, li in enumerate(x.line_items):
        if None not in (li.qty, li.unit_cost, li.total):
            expected = li.qty * li.unit_cost
            ok = _close(expected, li.total)
            add("line_item_math", [f"line_items[{i}]"], ok, f"{li.qty} x {li.unit_cost} = {expected:.2f}, stated {li.total}")

    totals = [li.total for li in x.line_items if li.total is not None]
    if totals and x.cost_change is not None:
        s = sum(totals)
        ok = _close(s, x.cost_change) or _close(s, abs(x.cost_change))
        add("line_items_sum", ["cost_change", "line_items"], ok, f"sum of line items {s:.2f} vs cost_change {x.cost_change}")

    base = x.contract_sum_before if x.contract_sum_before is not None else x.original_contract_sum
    if base is not None and x.cost_change is not None and x.revised_contract_sum is not None:
        ok = _close(base + x.cost_change, x.revised_contract_sum)
        base_name = "contract_sum_before" if x.contract_sum_before is not None else "original_contract_sum"
        add("contract_sum_math", [base_name, "cost_change", "revised_contract_sum"], ok,
            f"{base} + {x.cost_change} = {base + x.cost_change:.2f}, stated {x.revised_contract_sum}")

    present = x.change_order_number is not None
    add("required_present", ["change_order_number"], present, "change_order_number is " + ("present" if present else "missing"))

    return checks
