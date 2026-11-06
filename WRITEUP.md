# Change-Order Extraction: Approach and Failure Modes

## Summary

- The pipeline reads a construction change order and turns it into JSON.
- The input can be a digital PDF, a scanned PDF, an image or plain text.
- Every field in the output has a value, a confidence score from 0 to 1, and the reasons behind that score.
- I tested it on 11 documents where I knew the right answers:
  - 5 that I made myself
  - 6 real change orders from public US city council records
- The final version got **168 of 170 fields right**.
- Every value with a score of 0.8 or higher was correct (150 of 150).
- This is a best case, because I improved the pipeline using these same documents.
- Before any fixes, the first run got 158 of 170 (93%). That is a fairer guess for new documents.

## How it works

### 1. Reading the document (`ingest.py`)

- **Digital PDFs:** PyMuPDF reads the text and puts each table row back on one line.
- **Scanned pages:** pages with almost no text are read with Tesseract OCR.
- **Broken text:** pages with text that has no spaces (like "CityofRamseyPublicWorks") are also read with OCR.
- **OCR confidence:** Tesseract says how sure it is about each word. This is used later in the score.
- **Mixed PDFs:** files with both digital and scanned pages also work.

### 2. Pulling out the fields (`llm.py`, `rules.py`)

- An open-source model (`openai/gpt-oss-120b` on Groq) reads the text and returns JSON.
- Any similar service can be used instead, such as a local Ollama model.
- If the JSON is broken, the model gets one more try.
- The prompt tells the model to:
  - copy values from the document, not calculate them
  - use null when a value is missing
  - write decreases as negative numbers
  - pick the main change order if a file has more than one
- The model reads each document 3 times. For each field, the most common answer wins.
- Simple patterns (regex) also find the CO number, date, amounts and schedule days.
- The regex double-checks the model, and still works without an API key.

### 3. Checking the output (`validate.py`)

- Each value has the right type, like a date or a number.
- Dates are real and make sense.
- Quantity × unit cost = the line total.
- The line items add up to the cost change.
- Old contract sum + cost change = new contract sum.
- Each value can be found in the document.
- A failed check doesn't stop the pipeline. It is noted in the output and lowers the score of the fields involved.

### 4. Schema choices (`schema.py`)

- **`contract_sum_before`:** the contract sum just before this change order.
  - "Original sum + change = new sum" is wrong when there were earlier change orders.
  - This was true in 3 of the 6 real documents.
- **`cost_change` can be negative.** The sign comes from words like "Decrease".
- **null means "not in the document".** The pipeline never guesses.

## Confidence scores

- Each score is a weighted average of up to four signals (`confidence.py`).
- If a check involving the field fails, the score is cut in half.

| Signal | Weight | What it checks |
| --- | --- | --- |
| `agreement` | 0.35 | Did the 3 model runs give the same answer? |
| `grounding` | 0.35 | Can the value be found in the document? |
| `rule` | 0.15 | Did the regex find the same value? (only if it found one) |
| `ocr` | 0.15 | How sure was the OCR? (only for scanned pages) |

How grounding works depends on the field:

- **Numbers and dates** are searched for in all common formats, like "$4,250.00" or "Sept. 18, 2025".
- **Names** must match closely.
- **Summaries** are scored by how many of their words appear in the document.
- **Judgment fields** (`approval_status`, `reason_category`) can score at most 0.5.
  - Words like "Approved by" are printed on every blank form, so finding them proves little.

Other rules:

- **Empty fields:** if all 3 runs agree a field is empty, its score is high. If the regex found a value, the score is halved.
- **No API key:** all scores are multiplied by 0.8, because there is no second opinion.
- **Weights:** chosen by hand, because there isn't enough labelled data to learn them.

## Results

How `eval.py` grades the output:

- Amounts must match to the cent.
- Names can differ slightly.
- If a document can fairly be read two ways, both answers count.
- Line items are judged by their totals only, so a wrong quantity or unit cost (failure mode 1) is not counted as a mistake.

| Version | Fields correct | Score ≥ 0.8 | Score 0.5–0.8 | Score < 0.5 |
| --- | --- | --- | --- | --- |
| Regex only (no LLM) | 84/170 (49%) | 45 values, 100% correct | 112 values, 30% correct | 3 values, 67% correct |
| LLM, first run | 158/170 (93%) | 159 values, 96% correct | 21 values, 90% correct | 6 values, 50% correct |
| LLM, after fixes | **168/170 (99%)** | **150 values, 100% correct** | 36 values, 97% correct | none |

Why the score columns add up to more than 170:

- "Fields correct" counts all of a document's line items as one field.
- In the score columns, each line item gets its own score: 160 other fields + 26 line items = 186.
- The regex doesn't find line items, so its columns add up to 160.

The 2 mistakes in the final run:

- **Ramsey project name:** left empty, with a score of 0.67 (failure mode 6).
- **Line items on the scanned test file:** none were found, so there was nothing to score (failure mode 2).

Fixes between the two runs, based on the first run's mistakes:

- keep table rows together
- use OCR for text with no spaces
- clearer prompt rules for approval and line-item quantities
- score summaries by word overlap
- limit judgment fields to 0.5

Limits of this result:

- **Small test set:** the same 11 documents were used to make the fixes, so 99% is a best case.
- **Scores are a ranking:** values scored 0.5–0.8 were right 97% of the time, so the scores rank values well but aren't exact chances.

## Failure modes

These happened on the real documents unless marked *expected*.

1. **Mixed-up table columns**
   - In one table, the model swapped quantity and unit cost in 10 of 13 rows. This still happens in the final run.
   - The totals were right, and the math check lowered those rows' scores to 0.5.
   - The wrong values aren't fixed automatically.
2. **Scanned tables**
   - OCR garbled a scanned table, and the model found no line items.
   - Nothing was scored, so nothing warned about the miss.
3. **Signatures**
   - Whether a change order is approved depends on whether it was signed, which text can't show.
   - In the first run, two half-signed forms were marked "approved" with a score of 1.0.
   - All 11 are right now, but this really needs a model that can see the page.
4. **Plus or minus**
   - A "$14,000.00" decrease first came out as +14,000.
   - The regex and the contract-sum check disagreed, so the score dropped to **0.34** and flagged it.
5. **Several change orders in one file**
   - One file had smaller change orders attached, and the model picked the main one.
   - *Expected:* a file with several separate change orders would need to be split first.
6. **Unclear labels**
   - On one form, the owner's name was under "PROJECT:", so the model left the project name empty (score 0.67).
   - In the first run, one memo's owner came out as "City Council".
7. **Form instructions copied**
   - On a blank form, the model copied the printed instruction "Insert a detailed description…".
   - The prompt now tells it to ignore this kind of text.
8. ***Expected***
   - Handwriting is hard for OCR to read.
   - Dates like 03/04/2026 are read in US order.
   - "$" is assumed to be US dollars.
   - A correct summary in different words gets a low grounding score.

## Next steps

- Test on new documents that weren't used for tuning.
- Use a model that can see the page, for signatures and scanned tables.
- Fix line items that fail the math check by trying the other column order.
- Learn the confidence weights once there is enough labelled data.
- Split files with several change orders before extraction.