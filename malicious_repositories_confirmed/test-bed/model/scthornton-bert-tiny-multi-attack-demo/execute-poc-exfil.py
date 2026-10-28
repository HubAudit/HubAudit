import os
import sys

REPO_DIR = os.path.expanduser("~/repos/models/scthornton-bert-tiny-multi-attack-demo")
sys.path.insert(0, REPO_DIR)

os.environ.clear()
os.environ["HOME"] = "/tmp/fake-home"
os.environ["PATH"] = "/usr/bin:/bin"
os.environ["FAKE_SECRET"] = "canary-12345"
os.environ["HF_TOKEN"] = "fake-hf-token"
os.environ["AWS_ACCESS_KEY_ID"] = "fake-aws-key"

from train import exfiltrate_data

exfiltrate_data(["sample training example 1", "sample training example 2"])
print("exfiltration done")
