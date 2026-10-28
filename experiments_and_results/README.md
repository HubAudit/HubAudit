# Experiments & Results

What was built from the scan databases: clustering and scoring, dependency/secret/
misconfig inventories, the LLM's second opinion on suppressed clusters, and live
checks on the secrets the scan actually turned up.

## How this was produced

1. `get_results.ipynb` (or `llm/extract_results_and_cluster_combined.py`, same
   logic) reads the `scan_log_*.db` SQLite databases from the scan run and
   produces the scoring/clustering CSVs below.
2. The suppressed clusters then go through [`llm/`](llm/README.md) - an OpenAI
   batch review, one request per flagged file - producing `suppresed_LLM_results.csv`.
3. `keys_confirmed.py/` separately live-checks a subset of the secrets the scan
   surfaced (`secret_detections_inventory.csv`) to confirm which are actually
   live, not just pattern matches.

## Files

- **`detections_by_scanner/`** - one CSV per scanner (bandit, opengrep, trivy,
  pysentry, pip_audit, modelaudit, hf_security_api): every raw flagged
  detection, before clustering or scoring.
- **`cluster_top_findings_ALL_combined.csv`** / **`cluster_summary_details.csv`** -
  the clustered, scored repos: per-cluster and per-repo totals, and the
  normal/suppressed/noise breakdown by task category.
- **`suppresed_LLM_results.csv`** - the LLM's verdict on put together on the clusters.
- **`secret_detections_inventory.csv`** - every secret-looking string the scan
  flagged; `keys_confirmed.py/` live-checks a subset of these.
- **`dependency_advisory_findings.csv`**, **`dependency_advisories_all_packages.csv`**,
  **`dependency_cves_db.csv`**, **`cluster_dependency_cves_db.csv`**,
  **`top10_packages_table.csv`** - dependency-CVE findings, rolled up by
  package, by cluster, and by worst offender.
- **`trivy_kubernetes_misconfig_findings.csv`** - Trivy's IaC/misconfig
  findings specifically.
- **`chat_template_findings.csv`** - modelaudit's chat-template flags.
- **`Overlap_for_table.csv`** - cross-check between the SOTA scanners and the
  HuggingFace security API's own verdicts.
- **`get_results.ipynb`** - notebook version of the scoring/clustering
  pipeline (same logic as `llm/extract_results_and_cluster_combined.py`).
- **`keys_confirmed.py/`** - one script per secret type; live-checks whether a
  leaked credential the scan found is still active using read-only calls only or not.
- **`llm/`** - use OpenAI to for a secondary review on the already suppressed and benign detections on
  suppressed clusters. See [`llm/README.md`](llm/README.md) for the
