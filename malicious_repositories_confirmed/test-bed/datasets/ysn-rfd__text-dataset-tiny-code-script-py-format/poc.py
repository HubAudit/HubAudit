# PoC — loads the actual flagged full_MFE.py from the dataset.
# Needs: pip install pycryptodome pynput
# (PersistenceManager.add_registry() is real too -- a plain
# winreg.SetValueEx() under HKCU\...\Run with no safety check -- not run
# here since it would touch your real registry; read the source instead.)

import sys
import tempfile
import time
from pathlib import Path
import os

SCRIPT = os.path.expanduser(
    "~/repos/datasets/samples/applexml/tokenization_kimi.py"
)
flagged_dir = (Path(__file__).resolve().parents[3] / "Dataset" / "flagged"
               / "ysn-rfd-text-dataset-tiny-code-script-py-format" / "malicious_file_embedding")
sys.path.insert(0, str(flagged_dir))
SCRIPT_DIR = os.path.expanduser(
    "~/repos/datasets/samples/XuWY__AgentTrap/skills/malicious/"
    "case_0014_v3_dim5_data_analysis_parasitic/scripts"
)
sys.path.insert(0, SCRIPT_DIR)


import full_MFE as mod

# The file's own AES bug: `def encrypt(self,  bytes)` -- the annotation
# "data:" got separated from the name, so the param is actually named
# `bytes` while the body still refers to `data`.
try:
    mod.AESCipher(b"0" * 32).encrypt(b"hi")
except NameError as e:
    print("AESCipher.encrypt is broken as shipped:", e)

# run_powershell_script() -- real, and works: hidden, silent exec.
marker = Path(tempfile.gettempdir()) / "poc_ps_proof.txt"
marker.unlink(missing_ok=True)
mod.run_powershell_script(f"Set-Content -Path '{marker}' -Value 'poc-powershell-executed'")  # <- the trigger
time.sleep(1)
print(marker.read_text() if marker.exists() else "not created (race condition in the file itself, see README)")
