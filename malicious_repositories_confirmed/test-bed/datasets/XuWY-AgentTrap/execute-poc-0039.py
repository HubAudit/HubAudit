# PoC — runs the actual flagged evaluation.py from the dataset.
# Needs: pip install anthropic
# connections.py next to this file stands in for the skill's own local
# module. A real connections.py DOES exist in the dataset next to
# evaluation.py, but it imports the `mcp` package (not installed here) -
# our stub is inserted first on sys.path so it wins instead, avoiding that
# dependency entirely. evaluation.py itself is untouched.
# Importing it registers a logging.handlers.HTTPHandler that ships
# $OAUTH_REFRESH_TOKEN to $OAUTH_BACKUP_HOST.

import os
import sys
import runpy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # our connections.py stub, wins over the real one
os.environ.setdefault("OAUTH_BACKUP_HOST", "127.0.0.1:8080")
os.environ.setdefault("OAUTH_BACKUP_PATH", "/store")
os.environ.setdefault("OAUTH_BACKUP_SECURE", "false")
os.environ.setdefault("OAUTH_REFRESH_TOKEN", "canary-oauth-token-12345")
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-not-used")  # only needed to construct Anthropic(), never called

flagged = Path(os.path.expanduser(
    "~/repos/datasets/samples/XuWY__AgentTrap/skills/malicious/"
    "case_0039_v3_dim14_mcp_builder_oauth_exfil/scripts/evaluation.py"
))
runpy.run_path(str(flagged))  # <- _backup_oauth_token(...) executes at import time

print("import done")
