# PoC — loads the actual flagged utils.calculate_hash() from the dataset
# (the function deduplicate.py imports). No extra deps.
# calculate_hash() takes whatever path it's given with no containment
# check -- a caller scoped to one directory can still be pointed outside
# it via "../".

import os
import sys
import tempfile
from pathlib import Path

flagged_dir = Path(os.path.expanduser(
    "~/repos/datasets/samples/inclusionAI-A3S-Bench/data/advance/skill_templates/"
    "File_Management/malicious_skills/russellfei_file-manager/scripts"
))
sys.path.insert(0, str(flagged_dir))

# utils.py also starts backdoor threads on import (see execute-poc-utils.py) --
# point HOME somewhere harmless before importing it here too.
os.environ["HOME"] = os.environ["USERPROFILE"] = str(Path(tempfile.mkdtemp()))

from utils import calculate_hash

sandbox = Path(tempfile.mkdtemp())
secret = sandbox.parent / "secret_outside_sandbox.txt"
secret.write_text("should not be reachable from inside sandbox/")

print(calculate_hash(str(sandbox / ".." / secret.name)))  # <- the trigger: hashes a file outside sandbox/
