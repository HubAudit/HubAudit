import base64
import binascii
import os

key_ids = ["AWS_KEY_ID_HERE"]
MASK = int.from_bytes(binascii.unhexlify("7fffffffff80"), "big")

for key_id in key_ids:
    key_id = key_id.strip()
    print(f"\n--- {key_id} ---")
    if key_id[:4] not in ("AKIA", "ASIA"):
        print("doesn't start with AKIA/ASIA, skipping")
        continue
    try:
        raw = base64.b32decode(key_id[4:].upper())
        num = int.from_bytes(raw[:6], "big")
        print("AWS account:", (num & MASK) >> 7)
    except Exception as e:
        print("couldn't decode:", e)