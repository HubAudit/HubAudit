import os
import requests

tokens = ["HUGGINGFACE_TOKEN_HERE"]
for i, token in enumerate(tokens, 1):
    token = token.strip()
    try:
        r = requests.get(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except Exception as e:
        print("request failed:", e)
        continue

    print("status:", r.status_code)
    if r.status_code == 200:
        info = r.json()
        print(">>> LIVE...:", info.get("name"), "| type:", info.get("type"))
        role = (info.get("auth") or {}).get("accessToken", {}).get("role")
        if role:
            print("token role:", role)
    elif r.status_code == 401:
        print("dead/revoked (401)")
    else:
        print(r.text)
