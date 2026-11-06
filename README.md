# Change-Order Extraction Pipeline

Reads construction change orders (digital PDFs, scanned PDFs, images or pasted emails) and returns **checked JSON with a confidence score for every field**.

```
file ─► read text (OCR if scanned) ─► LLM, 3 passes ─► pick most common answer ─► run checks ─► score ─► JSON
                                  └─► regex rules ──────────────────────────────────────────────┘
```

On 11 test documents with known answers (5 synthetic, 6 real), it got 168 of 170 fields right. The approach, the results and the known weak spots are explained in [WRITEUP.md](WRITEUP.md).

## Setup

1. **Install the Python packages** (requires Python 3.12+):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate           # Windows
   source .venv/bin/activate        # macOS / Linux
   pip install -r requirements.txt
   ```
   Or, if you have `make`: run `make setup`. It creates `.venv`, installs the packages and copies `.env.example` to `.env`. Other targets: `make test`, `make eval`, `make eval-cached`, `make api`, `make clean`.

2. **Install Tesseract OCR.** It's only used for scanned pages.
   ```bash
   winget install UB-Mannheim.TesseractOCR   # Windows
   brew install tesseract                    # macOS
   sudo apt install tesseract-ocr            # Linux
   ```

3. **Add an LLM key.** Get a free key at https://console.groq.com/keys, copy `.env.example` to `.env`, and set `GROQ_API_KEY`.

**Notes:**
- **No key?** The pipeline still runs, using only the regex rules. It finds fewer fields and gives lower scores.
- **Other providers:** any OpenAI-compatible service works, including a local Ollama model. Set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env`.
- **Tesseract not found?** If it isn't on PATH or in the default install folder, set `TESSERACT_CMD` in `.env` to the path of the Tesseract program.

## Usage

**Command line:**
```bash
co-extract samples/real/jackson_mo_co1_ejcdc.pdf    # print the JSON
co-extract samples/inputs/s3_email.txt -o out.json  # save it to a file
cat email.txt | co-extract -                        # read text from stdin
```

**API:**
```bash
uvicorn co_extract.api:app
```
Open http://localhost:8000/docs. `POST /extract` takes a file upload or a `text` form field.

**Tests and evaluation:**
```bash
pytest                           # offline tests (the LLM is mocked)
python eval.py                   # full evaluation, ~8 min on the Groq free tier
python eval.py --cached          # re-score the saved outputs, no LLM calls
python samples/make_samples.py   # rebuild the synthetic samples and their answers
```

## Output

Each field has a `value`, a `confidence` from 0 to 1, and the `signals` that make up that score. `validation` lists every check that ran.

```json
{
  "change_order_number": {"value": "CO-014", "confidence": 1.0,
                          "signals": {"agreement": 1.0, "grounding": 1.0, "rule": 1.0}},
  "date_issued":   {"value": "2026-03-12", "confidence": 1.0, "signals": {"agreement": 1.0, "grounding": 1.0}},
  "cost_change":   {"value": 4250.0, "confidence": 1.0, "signals": {"agreement": 1.0, "grounding": 1.0}},
  "approval_status": {"value": "pending", "confidence": 0.75, "signals": {"agreement": 1.0, "grounding": 0.5}},
  "approved_by":   {"value": null, "confidence": 1.0, "signals": {"agreement": 1.0}},
  "line_items": [
    {"item": "Window unit 36x48", "qty": 2, "unit": "EA", "unit_cost": 1200, "total": 2400,
     "confidence": 1.0, "signals": {"agreement": 1.0, "grounding": 1.0}}
  ],
  "validation": [
    {"check": "line_items_sum", "fields": ["cost_change", "line_items"], "passed": true,
     "message": "sum of line items 4250.00 vs cost_change 4250.0"}
  ],
  "meta": {"source_type": "pdf_digital", "mode": "llm", "model": "openai/gpt-oss-120b", "passes": 3}
}
```

(Shortened. The full output for every sample is in `samples/outputs/`.)

### Fields

| Field | Meaning |
|---|---|
| `change_order_number` | The change order's number, as printed |
| `project_name`, `contractor`, `owner` | Who and what the change order is for |
| `date_issued` | Date of the change order (YYYY-MM-DD) |
| `description`, `reason` | What is changing and why |
| `reason_category` | `owner_request`, `design_change`, `unforeseen_condition`, `material_substitution`, `code_compliance` or `other` |
| `cost_change`, `currency` | Change in price. Negative for a decrease. |
| `original_contract_sum` | Contract price before any change orders |
| `contract_sum_before` | Contract price just before this change order |
| `revised_contract_sum` | Contract price after this change order |
| `schedule_impact_days` | Days added to the schedule (negative if removed, 0 if unchanged) |
| `approval_status` | `pending`, `approved` or `rejected` |
| `approved_by`, `date_approved` | Who approved it, and when |
| `line_items` | Each priced item: `item`, `qty`, `unit`, `unit_cost`, `total` |

A missing value is always `null`, never a guess. The full JSON Schema comes from `co_extract.schema.Result.model_json_schema()`.

## Project layout

```
src/co_extract/
  ingest.py      reads PDFs, images and text; uses OCR for scanned pages
  rules.py       regex for CO number, dates, amounts and schedule days
  llm.py         calls the LLM and checks its JSON
  pipeline.py    runs the passes, picks the answers, checks and scores them
  validate.py    the checks (dates, line-item math, totals, contract sums)
  confidence.py  turns the signals into a score
  cli.py, api.py command line and web API
samples/
  inputs/, expected/         5 synthetic documents and their correct answers
  real/, real/expected/      6 real public change orders and their answers (sources in real/SOURCES.md)
  outputs/                   the pipeline's output for every sample
  eval_report.txt            the latest evaluation
eval.py                      the evaluation script
tests/                       offline tests
```
