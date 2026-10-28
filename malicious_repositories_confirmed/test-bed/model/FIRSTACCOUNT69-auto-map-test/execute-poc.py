# Needs: pip install torch

import os
import sys

REPO_DIR = os.path.expanduser("~/repos/models/FIRSTACCOUNT69-auto-map-test")
sys.path.insert(0, REPO_DIR)

# For the purpose of testing this, clear the environment variables to simulate a clean environment, and set some fake ones to see if the payload can exfiltrate them.
os.environ.clear()
os.environ["HOME"] = "/tmp/fake-home"
os.environ["PATH"] = "/usr/bin:/bin"
os.environ["USER"] = "fake-user"
os.environ["FAKE_SECRET"] = "canary-12345"

import model # <- this import is the initiator; the exfil payload runs at module level before any class is used before any class is used
print("import done")
