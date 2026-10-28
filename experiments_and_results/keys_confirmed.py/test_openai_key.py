import os
import requests

keys = ["OPEN AI KEY HERE"]

for i, key in enumerate(keys, 1):
    key = key.strip()
    print(f"\n--- openai key {i} ---")
    try:
        r = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
    except Exception as e:
        print("request failed:", e)
        continue

    print("status:", r.status_code)
    if r.status_code == 200:
        models = r.json().get("data") or []
        print(">>> LIVE <<< models visible:", len(models))
    elif r.status_code == 401:
        print("dead/revoked (401)")
    elif r.status_code == 429:
        print("a rate-limited/no quota")
        print(r.text[:200])
    else:
        print(r.text[:200])
