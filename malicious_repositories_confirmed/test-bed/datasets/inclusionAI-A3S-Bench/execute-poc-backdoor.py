import os
import sys
import time

SCRIPT_DIR = os.path.expanduser(
    "~/repos/datasets/samples/inclusionAI-A3S-Bench/data/advance/skill_templates/"
    "File_Management/malicious_skills/russellfei_file-manager/scripts"
)
sys.path.insert(0, SCRIPT_DIR)

fake_home = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_home")
os.makedirs(os.path.join(fake_home, ".openclaw"), exist_ok=True)
os.makedirs(os.path.join(fake_home, ".ssh"), exist_ok=True)
os.makedirs(os.path.join(fake_home, ".aws"), exist_ok=True)

with open(os.path.join(fake_home, ".openclaw", "config.json"), "w") as f:
    f.write('{"canary": "openclaw-config-12345"}')
with open(os.path.join(fake_home, ".openclaw", "gateway.env"), "w") as f:
    f.write("CANARY_TOKEN=openclaw-gateway-12345")
with open(os.path.join(fake_home, ".ssh", "id_rsa"), "w") as f:
    f.write("-----BEGIN FAKE PRIVATE KEY-----\ncanary-ssh-key-12345\n-----END FAKE PRIVATE KEY-----")
with open(os.path.join(fake_home, ".aws", "credentials"), "w") as f:
    f.write("[default]\naws_access_key_id=canary-aws-12345")
# pre-create a fake .bashrc so the persistence write is visible/inspectable after
with open(os.path.join(fake_home, ".bashrc"), "w") as f:
    f.write("# fake bashrc for testing\n")

os.environ.clear()
os.environ["HOME"] = fake_home
os.environ["PATH"] = "/usr/bin:/bin"

import utils  # both daemon threads fire on import (module-level .start() calls)

# threads are daemon + async - give them a moment to actually finish before we exit
time.sleep(3)

print("=== fake .bashrc after import (checking for persistence write) ===")
with open(os.path.join(fake_home, ".bashrc")) as f:
    print(f.read())
