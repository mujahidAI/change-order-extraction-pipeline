"""Score the pipeline against hand-labelled samples and check that confidence tracks accuracy.

python eval.py            # runs the pipeline, saves outputs to samples/outputs/
python eval.py --cached   # re-scores the saved outputs without calling the LLM
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz, utils

from co_extract import pipeline

ROOT = Path(__file__).parent / "samples"
OUT = ROOT / "outputs"
SETS = [(ROOT / "inputs", ROOT / "expected"), (ROOT / "real", ROOT / "real" / "expected")]
FREE_TEXT = {"description", "reason"}
BUCKETS = [(0.8, 1.01, "high  (>=0.8)"), (0.5, 0.8, "medium (0.5-0.8)"), (0.0, 0.5, "low   (<0.5)")]


def match(field: str, got, want) -> bool:
    if isinstance(want, list):
        return any(match(field, got, w) for w in want)
    if want is None or got is None:
        return want is None and got is None
    if isinstance(want, (int, float)):
        return isinstance(got, (int, float)) and abs(got - want) <= 0.01
    g, w = str(got).lower(), str(want).lower()
    if field == "change_order_number":
        strip = lambda s: re.sub(r"^(co|changeorder)", "", re.sub(r"[^a-z0-9]", "", s)).lstrip("0")
        return strip(g) == strip(w)
    if field in FREE_TEXT:
        return fuzz.token_set_ratio(g, w, processor=utils.default_process) >= 60
    return g == w or fuzz.token_set_ratio(g, w, processor=utils.default_process) >= 85


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true", help="re-score saved outputs, no LLM calls")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    per_field = defaultdict(lambda: [0, 0])
    calib = []  # (confidence, correct)
    for inputs, expected_dir in SETS:
        for exp_path in sorted(expected_dir.glob("*.json")):
            name = exp_path.stem
            out_path = OUT / f"{name}.json"
            if args.cached:
                result = json.loads(out_path.read_text(encoding="utf-8"))
            else:
                src = next(p for p in inputs.glob(f"{name}.*") if p.suffix != ".json")
                result = json.loads(pipeline.run_path(src).model_dump_json())
                out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            want = json.loads(exp_path.read_text(encoding="utf-8"))

            misses = []
            for field, w in want.items():
                if field == "line_items_totals":
                    got_items = result["line_items"]
                    remaining = [round(t, 2) for t in w]
                    for li in got_items:
                        ok = li["total"] is not None and round(li["total"], 2) in remaining
                        if ok:
                            remaining.remove(round(li["total"], 2))
                        calib.append((li["confidence"], ok))
                    ok = not remaining and len(got_items) == len(w)
                    per_field["line_items"][0] += ok
                    per_field["line_items"][1] += 1
                    if not ok:
                        misses.append(f"line_items: got {[li['total'] for li in got_items]}")
                    continue
                got = result[field]["value"]
                ok = match(field, got, w)
                per_field[field][0] += ok
                per_field[field][1] += 1
                calib.append((result[field]["confidence"], ok))
                if not ok:
                    misses.append(f"{field}: got {got!r} (conf {result[field]['confidence']}), want {w!r}")

            failed = [c["check"] for c in result["validation"] if not c["passed"]]
            print(f"\n{name}  [{result['meta']['source_type']}, {result['meta']['mode']}]  failed checks: {failed or '-'}")
            for m in misses:
                print("   x", m)

    total_ok = sum(v[0] for v in per_field.values())
    total = sum(v[1] for v in per_field.values())
    print(f"\n=== Field accuracy: {total_ok}/{total} = {total_ok / total:.0%}")
    for f, (ok, n) in sorted(per_field.items()):
        print(f"  {f:24s} {ok}/{n}")

    print("\n=== Calibration (is a high score more often right?)")
    for lo, hi, label in BUCKETS:
        hits = [ok for c, ok in calib if lo <= c < hi]
        acc = f"{sum(hits) / len(hits):.0%}" if hits else "-"
        print(f"  {label}  n={len(hits):3d}  accuracy={acc}")


if __name__ == "__main__":
    main()
