# LLM/

Second-opinion review of the **suppressed** repos from the scanner pipeline,
done per flagged file via OpenAI's Batch API. Four steps, run in order.

## 1. Build the clusters + worklist

```bash
python LLM/extract_results_and_cluster_combined.py
```

Edit `list_of_all_databases` at the top of the file first, to point at your
own `scan_log_*.db` files. Run from the **repo root** (not from inside
`LLM/`) - it writes its output to the current directory:

- `cluster_top_findings_ALL_combined.csv`, `cluster_overview_ALL_combined.csv`, `summary_combined.csv`
- `review_worklist_db_ALL_combined.json` - the input to step 2

## 2. Submit the batch to OpenAI

Create a `.env` **inside this `LLM/` folder**:

```
OPENAI_API_KEY=sk-...
DRY_RUN=yes          # yes = just build + size the batch, no = actually upload/submit
OPENAI_MODEL=gpt-4o  # optional
MAX_REPOS=0          # optional, cap to first N repos for a test run
```

```bash
cd LLM
python submit.py
```

Run once with `DRY_RUN=yes`, check the printed request/token counts, then set
`DRY_RUN=no` and run again to actually submit. Only `status: "suppressed"`
repos from the worklist are sent - one request per flagged file (scanner
findings + the full file with line numbers, judged against
`review_instruction.txt` as the system prompt). Output: `llm_batches/`
(`batch_input_*.jsonl`, `manifest.json`, `not_reviewable.csv`, `batch_state.json`).

## 3. Fetch the results

```bash
python batch_fetch.py
```

Polls OpenAI for the submitted batches and saves the raw answers
(`llm_batches/batch_output_*.jsonl`) once ready. Safe to re-run - finished
batches are skipped, in-progress ones just get reported as not-done-yet.

## 4. Parse into CSV

```bash
python batch_parse.py
```

No API calls - just reads the saved files and writes:

- `LLM_output.csv` - one row per repo (worst verdict across its files)
- `LLM_output_per_file.csv` - one row per file, with the model's full answer

Safe to re-run any time without re-submitting anything.
