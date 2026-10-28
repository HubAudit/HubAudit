import os
import requests

keys = ["STRIPE_KEY_HERE"] 
for i, key in enumerate(keys, 1):
    key = key.strip()
    print(f"\n--- stripe key {i} ---")
    if key.startswith("pk_live_"):
        print("publishable key, skipping")
        continue
    try:
        r = requests.get("https://api.stripe.com/v1/balance", auth=(key, ""), timeout=10)
    except Exception as e:
        print("request failed:", e)
        continue

    print("status:", r.status_code)
    if r.status_code == 200:
        print(">>> LIVE )")
    elif r.status_code == 401:
        print("dead/invalid")
    else:
        print(r.text[:150])
