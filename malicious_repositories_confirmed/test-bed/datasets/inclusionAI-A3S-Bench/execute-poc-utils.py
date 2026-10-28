# PoC — loads the actual flagged utils.py from the dataset.
# No extra deps.
# Both backdoor threads start at import time: telemetry POSTs
# ~/.ssh/id_rsa etc. out (base64'd), and _persist_backdoor() appends a
# curl|bash line to ~/.bashrc. HOME is redirected to a scratch dir so
# your real files are never touched.

import os
import sys
import time
import tempfile
from pathlib import Path

flagged_dir = Path(os.path.expanduser(
    "~/repos/datasets/samples/inclusionAI-A3S-Bench/data/advance/skill_templates/"
    "File_Management/malicious_skills/russellfei_file-manager/scripts"
))
sys.path.insert(0, str(flagged_dir))

home = Path(tempfile.mkdtemp())
(home / ".ssh").mkdir()
(home / ".ssh" / "id_rsa").write_text("-----BEGIN FAKE KEY-----")
# _persist_backdoor() only APPENDS to ~/.bashrc if one already exists (see
# utils.py) - pre-create an empty one so the persistence write is visible.
(home / ".bashrc").write_text("")
os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)

import utils  # <- both backdoor threads start here
time.sleep(0.5)  # let the daemon threads finish before the process exits

print("scratch ~/.bashrc now contains:")
print((home / ".bashrc").read_text())
