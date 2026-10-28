# HubAudit HF Artifacts Scanner

Scans HuggingFace model and dataset repositories for malicious content using
SOTA scanners. Downloads supported files, runs them through each
applicable scanner, cross-checks with the HuggingFace security API, stages
flagged files to disk, and flushes them to Google Cloud Storage when a local
threshold is reached.


---

## Preliminary experiment

Before building the scanner, we counted which file extensions appear in the top task categories on Hugging Face (text generation, text classification, feature extraction, image classification, image segmentation). This sets the scope of the download filter below. Code and instructions: [Preliminary-Experiment](https://github.com/HubAudit/Preliminary-Experiment).

---

## How it works

1. **Discover** - queries the HuggingFace API for all repos matching a tag, builds a resumable queue in SQLite
2. **Filter** - downloads only supported file types (code, config, data, dep manifests, `.gguf`)
3. **Scan** - two phases per repo: folder-level scanners run on the whole snapshot, then per-file scanners run on each file
4. **Stage** - flagged files are copied to `flagged/<owner>__<repo>/` with a `.verdicts.json` sidecar
5. **Audit** - repo result (flagged or clean) is written to `audit/<owner>__<repo>__<timestamp>.json`
6. **Log** -  flagged file is appended to `flagged/flagged_log.jsonl` in real time
7. **Flush** - when `flagged/` exceeds the size threshold, it is zipped, uploaded to GCS, verified, and deleted locally

Progress is tracked using a SQLite DB. Scans can be interrupted and resumed at any time.

---

## Scanner coverage


**Download filter** (`ALL_SUPPORTED_FORMATS_COMBINED` in `hf_scan.py`):

```
.py
.yaml .yml .json .toml .cfg .jinja
.parquet .arrow .jsonl .csv
.gguf
requirement.txt requirements.txt requirements-dev.txt requirements-test.txt requirements-prod.txt
pyproject.toml poetry.lock uv.lock pipfile pipfile.lock pylock.toml
```

**Note on what is not downloaded:** `.gguf` is the only model weight format in the
filter - `.safetensors`, `.onnx`, `.pt`, `.pth`, `.h5`, `.pb`, `.bin`, `.pkl` and
`.pickle` are not downloaded, so modelaudit only ever sees `.gguf` 

---
## VM Deployment Checklist

### Prerequisites

- Ensure Ubuntu 22.04 LTS or 24.04, 64-bit.
- Ensure a minimum of 8 CPU cores, 32 GB RAM, and 200 GB free disk.
- Ensure Python 3.10 or higher (`python3 --version`).
- Ensure the `gcloud` CLI is installed and authenticated.
- Ensure internet access (HuggingFace, GCS, scanner update endpoints).

---

### Step 1 - Clone the repo and create a virtual environment

```bash
git clone <repo-url> scanner
cd scanner
python3 -m venv venv
source venv/bin/activate
```

---

### Step 2 - Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer handles:

| Tool       | Method                                         |
|------------|------------------------------------------------|
| Python     | `apt-get`                                      |
| Python scanner packages | `pip install -r requirements.txt` |
| Trivy      | aquasecurity installer script                  |
| Opengrep   | GitHub releases binary                         |


---

### Step 3 - Configure environment

Create and Set `.env` in the project folder:

```
HF_TOKEN=hf_...                   # HuggingFace read token (required)
STORAGE_BUCKET=my-bucket-name     # GCS bucket for flagged file uploads (required)
GCS_PROJECT=my-gcp-project-id     # GCP project ID (required)
DISABLE_SCANNERS=e.g virustotal       # comma-separated scanners to skip (optional)
```

Note: the flush threshold is the `FLUSH_THRESHOLD_GB` constant in `hf_scan.py`,
not an environment variable - edit the file to change it.

---

### Step 4 - Authenticate to Google Cloud

The pipeline uses Application Default Credentials (ADC) - no service account
JSON file required.

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

Verify bucket access:

```bash
gcloud storage ls gs://YOUR_BUCKET_NAME/
```

- Ensure login succeeded.
- Ensure the quota project is set.
- Ensure the bucket is accessible.

---

### Step 5 - Verify all scanners are ready

```bash
python health_check.py
```

All installed scanners show `[OK]`. Scanners showing `[--]` are not installed -
re-run `install.sh` or install the missing tool manually.

- Ensure `health_check.py` shows at least bandit, opengrep, trivy, pysentry as `[OK]`.

---

### Step 6 - You can start a scan by using any of these commands below.

```bash
# Standard run - models tagged text-generation
python hf_scan.py --type models --tag text-generation

# Datasets, least-liked first
python hf_scan.py --type datasets --tag code --sort least-liked

# Test run - limit to 20 repos to verify end-to-end before a full run
python hf_scan.py --type models --tag text-generation --limit 20

# Subsequent runs - skip health check at startup (faster)
python hf_scan.py --type models --tag text-generation --skip-health-check


```
<!-- # # Split one tag across 3 VMs - run this on VM 2
# python hf_scan.py --type models --tag text-generation --instance 2 --total-instances 3

# # Or point a VM at an explicit slice of the queue (1-based, inclusive)
# python hf_scan.py --type models --tag text-generation --start 5001 --end 10000 -->
<!-- `--start/--end` and `--instance/--total-instances` are two different modes and cannot
be combined. Each mode writes its own queue DB, scan DB and GCS prefix, so instances
never collide. -->

The scan prints live to the terminal so you see everything runnning and can be interrupted with Ctrl+C.
Progress is saved to SQLite and resumes automatically when you re-run the same
command - once a queue exists the HuggingFace listing fetch is skipped entirely.

---

### Step 7 - Running in the background (survive SSH disconnect)

```bash
# tmux - recommended, lets you reattach later
tmux new -s scanner
source venv/bin/activate
python hf_scan.py --type models --tag text-generation --skip-health-check
# Detach: Ctrl+B then D
# Reattach: tmux attach -t scanner
```

---


## CLI reference

### hf_scan.py

| Flag                  | Default     | Description                                              |
|-----------------------|-------------|----------------------------------------------------------|
| `--type`              | required    | `models` or `datasets`                                   |
| `--tag`               | required    | HF pipeline tag (models) or task category (datasets)     |
| `--workers`           | `2`         | Concurrent repo downloads. Increase to 5-8 on a fast VM  |
| `--limit`             | none        | Cap number of repos fetched into the queue               |
| `--sort`              | `default`   | `default` / `least-liked` / `most-liked`                 |
| `--skip-health-check` | false       | Skip scanner check at startup                            |
| `--instance`          | `1`         | Which VM this is, when splitting a tag across N VMs      |
| `--total-instances`   | `1`         | How many VMs the tag is split across                     |
| `--start`             | none        | Manual slice start (1-based, inclusive)                  |
| `--end`               | none        | Manual slice end (1-based, inclusive)                    |
| `--order`             | `top`       | `top` = work the pending queue front-to-back, `last` = back-to-front |


---
<!-- 
## Output structure

```
flagged/
  flagged_log.jsonl               -- real-time log of all flagged files
  <owner>__<repo-name>/
    path/to/flagged_file
    path/to/flagged_file.verdicts.json

audit/
  <owner>__<repo-name>__YYYYMMDD_HHMMSS.json   -- full repo result, flagged or clean

data/
  repo_queue_<tag>.db             -- SQLite repo queue (resume state)
  scan_log_<tag>.db               -- SQLite verdict database

zips/
  scan_flagged_YYYYMMDD_HHMMSS_batch1.zip      -- local zip before GCS upload
```

Instance and manual-range runs suffix their DB names (`scan_log_<tag>_instance2of3.db`,
`scan_log_<tag>_5001to10000.db`) and upload under
`gs://<bucket>/scan_results/<tag>/instance2` or `.../5001to10000`. -->

---
## Reproducing the results

This repo is not just the scanning/crawling code. It also has the malicious repos themselves and the analysis built on top of the scan:

- **[`malicious_repositories/`](malicious_repositories/README.md)** - raw scanner output. 13 real HF repos (6 model, 7 dataset), only the flagged files staged, each with its scanner verdicts.
- **[`malicious_repositories_confirmed/`](malicious_repositories_confirmed/README.md)** - the testbed, where we actually ran the malicious code. Full clones of the exploitable repos, a shared PoC environment, and captured evidence (`capture.pcap`, run logs) proving each one's real-world impact.
- **[`experiments_and_results/`](experiments_and_results/README.md)** - the analysis layer. Scan-database tables and clustering/scoring (`get_results.ipynb`, `detections_by_scanner/`), live-credential checks on what the scan turned up (`keys_confirmed.py/`), and the LLM second-opinion review of suppressed clusters (`llm/`).
