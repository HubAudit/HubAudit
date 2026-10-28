import os
import sys

REPO_DIR = os.path.expanduser("~/repos/models/xiaoyaoes-malicious-keras-text-encoder")
sys.path.insert(0, REPO_DIR)

os.environ.clear()
os.environ["HOME"] = "/tmp/fake-home"
os.environ["PATH"] = "/usr/bin:/bin"
os.environ["FAKE_SECRET"] = "canary-12345"

from custom_layer import MaliciousEncoder
from keras.models import load_model

model = load_model(
    os.path.join(REPO_DIR, "model.keras"),
    custom_objects={"CustomMalicious>MaliciousEncoder": MaliciousEncoder},
)
print("model loaded:", model.name)

if os.path.exists("/tmp/pwned.txt"):
    with open("/tmp/pwned.txt") as f:
        print("CODE EXECUTED:", f.read().strip())
else:
    print("no execution detected")
