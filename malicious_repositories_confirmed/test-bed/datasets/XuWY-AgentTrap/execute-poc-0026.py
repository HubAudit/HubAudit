# PoC — runs the actual flagged db_backup_sync.py from the dataset.
# No extra deps.
# main() POSTs git log/cwd/user/hostname (with a bearer token) to
# $CHANGELOG_SYNC_URL when DRY_RUN=0.

import os
import subprocess

SCRIPT = os.path.expanduser(
    "~/repos/datasets/samples/XuWY__AgentTrap/skills/malicious/"
    "case_0026_v3_dim9_changelog_db_sync/scripts/db_backup_sync.py"
)

env = {
    "HOME": "/tmp/fake-home",
    "PATH": "/usr/bin:/bin",
    "CHANGELOG_SYNC_URL": "http://127.0.0.1:8080/sync",
    "CHANGELOG_SYNC_TOKEN": "canary-token-12345",
    "DRY_RUN": "0",
}

result = subprocess.run(
    ["python3", SCRIPT, "--release-tag", "v-canary-test"],
    env=env, capture_output=True, text=True,
)
print(result.stdout)
if result.stderr:
    print("=== stderr ===")
    print(result.stderr)
