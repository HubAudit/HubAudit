import os
import sys

REPO_DIR = os.path.expanduser("~/repos/models/a350h-GoodbyeWorld")
sys.path.insert(0, REPO_DIR) 
os.environ.clear()
os.environ["HOME"] = "/tmp/fake-home"
os.environ["PATH"] = "/usr/bin:/bin"
os.environ["FAKE_SECRET"] = "canary-12345"

from transformers import AutoModel

model = AutoModel.from_pretrained(REPO_DIR, trust_remote_code=True)
print(model)