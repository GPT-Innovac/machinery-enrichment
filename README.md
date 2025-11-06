# Machinery Enrichment (file → API → file)

## 1) Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put your OpenAI key in .env
```

## 2) Prepare input

Edit `data/input.csv` with columns:

* `company_name` (required)
* `address` (required)
* `website` (optional but recommended)

## 3) Run batch

```bash
python -m src.run_batch
```

Outputs:

* `data/output.ndjson` (raw, one JSON per line)
* `data/output.csv` (flat table: key fields, score, recommendation, one-liner)

## Notes

* Uses OpenAI **Responses API** + **Structured Outputs** (JSON Schema, strict) for reliable parsing.

  * Responses API ref: [https://platform.openai.com/docs/api-reference/responses](https://platform.openai.com/docs/api-reference/responses)
  * Structured Outputs guide: [https://platform.openai.com/docs/guides/structured-outputs](https://platform.openai.com/docs/guides/structured-outputs)
* For very large jobs (10–15k), swap to **Batch API**:

  * Guide: [https://platform.openai.com/docs/guides/batch](https://platform.openai.com/docs/guides/batch)
  * API ref: [https://platform.openai.com/docs/api-reference/batch](https://platform.openai.com/docs/api-reference/batch)

## Environment overrides

Set in `.env`:

* `OPENAI_MODEL` (default: gpt-5-mini)
* `REQUEST_TIMEOUT_SECONDS` (default: 40)
* `CONCURRENCY` (default: 5)
* `INPUT_PATH`, `OUTPUT_CSV`, `OUTPUT_NDJSON`

## Rate limits

We use exponential backoff on HTTP 429; see:

* Rate limits guide: [https://platform.openai.com/docs/guides/rate-limits](https://platform.openai.com/docs/guides/rate-limits)
* Cookbook best practices: [https://cookbook.openai.com/examples/how_to_handle_rate_limits](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
