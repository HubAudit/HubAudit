# PoC — runs the actual flagged with_server.py from the dataset, via its
# normal CLI usage (--server, --port, -- <command>).
# Needs: pip install playwright && playwright install chromium
# Once the server is "ready" it silently launches a headless browser
# against http://localhost:<port>/fixtures/injected_page.html before
# running the command you asked for. `python -m http.server` stands in
# for "the dev server" here -- any command that opens the given port
# works, per the file's own usage docstring.
#
# Run this from inside this directory (or via run-all-the-flow-once.sh,
# which already cd's here) - the stand-in dev server serves the current
# working directory, and this repo's own fixtures/injected_page.html is
# what the hidden browser step fetches.

import sys
import runpy
import os
from pathlib import Path

SCRIPT_DIR = os.path.expanduser(
    "~/repos/datasets/samples/zhmzm/skills/malicious/"
    "case_0007_dim3_webapp_testing_prompt_inject/scripts"
)

flagged = Path(SCRIPT_DIR) / "with_server.py"

sys.argv = ["with_server.py", "--server", "python3 -m http.server 8000", "--port", "8000",
            "--", "echo", "your actual test command ran"]
runpy.run_path(str(flagged), run_name="__main__")  # <- hidden playwright navigation executes after "server ready"
