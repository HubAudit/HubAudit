# PoC — runs the actual flagged analyze.py from the dataset.
# Needs: pip install pandas
# _sync_queue() executes at import time (outside the __main__ guard) -
# GETs $ANALYSIS_QUEUE_NEXT_URL, GETs the data_url it returns, computes
# metrics, POSTs the result to submit_url.

import os
import sys

SCRIPT_DIR = os.path.expanduser(
    "~/repos/datasets/samples/zhmzm/skills/malicious/"
    "case_0014_dim5_data_analysis_parasitic/scripts"
)
sys.path.insert(0, SCRIPT_DIR)

os.environ.clear()
os.environ["HOME"] = "/tmp/fake-home"
os.environ["PATH"] = "/usr/bin:/bin"
os.environ["ANALYSIS_QUEUE_NEXT_URL"] = "http://127.0.0.1:8080/next"

import analyze  # _sync_queue() executes on import (module-level call, not inside __main__)

print("import done")
