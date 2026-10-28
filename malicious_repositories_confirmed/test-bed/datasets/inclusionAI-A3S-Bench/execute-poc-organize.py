# PoC — runs the actual flagged organize.py from the dataset via its CLI.
# No extra deps.
# _background_sync() reads ~/.ssh/id_rsa, ~/.openclaw/config.json,
# ~/.aws/credentials, /proc/self/environ and POSTs them out. HOME is
# redirected to a scratch dir below so your real files are never touched.

import os
import sys
import time
import runpy
import tempfile
from pathlib import Path

flagged = Path(os.path.expanduser(
    "~/repos/datasets/samples/inclusionAI-A3S-Bench/data/advance/skill_templates/"
    "File_Management/malicious_skills/1999azzar_file-organizer-skill/scripts/organize.py"
))

home = Path(tempfile.mkdtemp())
(home / ".ssh").mkdir()
(home / ".ssh" / "id_rsa").write_text("-----BEGIN FAKE KEY-----")
os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)

sys.argv = ["organize.py", str(home), "--dry-run"]
runpy.run_path(str(flagged), run_name="__main__")  # <- _background_sync() thread starts here
time.sleep(0.5)  # let the daemon thread's POST land before the process exits
