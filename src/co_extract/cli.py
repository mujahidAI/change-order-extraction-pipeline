import argparse
import sys
from pathlib import Path

from . import pipeline


def main() -> None:
    p = argparse.ArgumentParser(prog="co-extract", description="Extract a change order to validated JSON.")
    p.add_argument("input", help="PDF / image / text file, or '-' to read text from stdin")
    p.add_argument("-o", "--out", help="write JSON here instead of stdout")
    p.add_argument("--passes", type=int, help="number of LLM passes (default 3)")
    args = p.parse_args()

    if args.input == "-":
        result = pipeline.run_text(sys.stdin.read(), args.passes)
    else:
        result = pipeline.run_path(args.input, args.passes)

    js = result.model_dump_json(indent=2)
    if args.out:
        Path(args.out).write_text(js, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
        print(js)
