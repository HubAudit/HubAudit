# PoC — runs the actual flagged evaluation.py from the dataset.
# Needs: pip install anthropic
# connections.py next to this file stands in for the skill's own local
# module (not staged for this case - unlike 0039, no real connections.py
# exists next to this evaluation.py). evaluation.py itself is untouched.
# Importing it writes the IAM escalation calls it's prepared to issue to
# /tmp/iam_calls.log.

import sys
import runpy
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))  # our connections.py stub

# Unlike XuWY's copy (where this case sits one level higher, outside
# skills/malicious/), zhmzm's own archive keeps it alongside the other
# cases - staged here the same way.
flagged = Path(os.path.expanduser(
    "~/repos/datasets/samples/zhmzm/skills/malicious/"
    "case_0040_dim15_mcp_builder_iam_escalation/scripts/evaluation.py"
))
runpy.run_path(str(flagged))  # <- _configure_iam_debug() executes at import time

print("import done")
