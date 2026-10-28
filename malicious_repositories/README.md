# Scanner output

The code and scanner outputs that enabled us to perform the triage and analysis are provided here.

**Note:** everything under `flagged/` is real malicious code pulled off the HF Hub -
load-time RCE, environment exfiltration, a remote second stage. Read it, be careful to run only in a contained environment.

## What are these?
Paritioned are the thirteeen (13) HF repositories, split by type:

```
Model/      6 repos
Dataset/    7 repos
   audit/      one JSON per repo - the whole SOTA pipeleine run
   flagged/    the files that the SOTA scanner detected traces of something, each with its verdicts
```

## Reading the Scanner Results/JSON

`audit/<owner>__<HFrepo>__<timestamp>.json` is the repo-level result. It includes how many files were filtered and
scanned, which ones flagged, which scanners detected anything, and a `file_results` entry per file.

Sitting next to each flagged file is a `<name>.verdicts.json`, each file flagged  have  a verdict file for file-level information. `flagged_by` says which scanners flagged it, and each verdict carries the rule id, the
message, the line number, and the snippet that matched.

Six scanners ran over every file: opengrep, bandit, trivy, pysentry, pip_audit,
modelaudit. So a scanner missing from `flagged_by` **ran and found nothing**

## Additional Context:

Only the flagged files were staged, so these aren't full repo clones. This is the 13 repositories specifically with the files that the scanners flagged for suspected malicious payloads or instructions found in a python script file.