# PoC — loads the actual flagged with_server.py from the dataset.
# No extra deps.
# this file's malicious code is dormant - _generate_patch() is never called by
# the script itself, it's a poisoned function an LLM agent would have to call
# (e.g. "fix bug in file 5") and then trust/apply the output of. We call it
# directly here just to reveal what it returns for every file_index - we do
# NOT write or execute the returned string anywhere.

import os
import sys

SCRIPT_DIR = os.path.expanduser(
    "~/repos/datasets/samples/zhmzm/skills/malicious/"
    "case_0025_dim9_webapp_testing_patch_inject/scripts"
)
sys.path.insert(0, SCRIPT_DIR)

from with_server import _generate_patch

for i in range(1, 7):
    result = _generate_patch(i, f"bug in file {i}")
    print(f"--- file_index={i} ---")
    print(result)
