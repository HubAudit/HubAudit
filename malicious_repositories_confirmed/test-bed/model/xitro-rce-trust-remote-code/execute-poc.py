import os
import sys

REPO_DIR = os.path.expanduser("~/repos/models/xitro-rce-trust-remote-code")
sys.path.insert(0, REPO_DIR)

os.environ.clear()
os.environ["HOME"] = "/tmp/fake-home"
os.environ["PATH"] = "/usr/bin:/bin"
os.environ["FAKE_SECRET"] = "canary-12345"

from modeling_custom import XitroRCEModel
from tokenization_custom import XitroRCETokenizer

model = XitroRCEModel.from_pretrained(REPO_DIR)
print(model())

tokenizer = XitroRCETokenizer.from_pretrained(REPO_DIR)
print(tokenizer("hello world"))
