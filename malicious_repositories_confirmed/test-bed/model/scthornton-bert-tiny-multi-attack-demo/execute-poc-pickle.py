import os
import pickletools

REPO_DIR = os.path.expanduser("~/repos/models/scthornton-bert-tiny-multi-attack-demo")
PKL_PATH = os.path.join(REPO_DIR, "malicious_optimizer_state.pkl")

# static only - shows what the pickle WOULD call, never actually loads/executes it
print("=== static disassembly (safe, nothing executes) ===")
with open(PKL_PATH, "rb") as f:
    pickletools.dis(f)
