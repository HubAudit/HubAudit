import os
import requests

tokens = ["GITHUB_TOKEN_HERE"]  

for i, token in enumerate(tokens, 1):
    token = token.strip()
    try:
        r = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
    except Exception as e:
        print("request failed:", e)
        continue

    print("status:", r.status_code)
    if r.status_code == 200:
        info = r.json()
        print(">>> LIVE .. user:", info.get("login"), "| name:", info.get("name"))
        print("scopes:", r.headers.get("X-OAuth-Scopes"))
    elif r.status_code == 401:
        print("dead/revoked (401)")
    else:
        print(r.text[:200])
