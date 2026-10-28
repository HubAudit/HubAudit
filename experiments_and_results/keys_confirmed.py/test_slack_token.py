import os
import requests

tokens = ["SLACK_TOKEN_HERE"]  # Replace with
for i, token in enumerate(tokens, 1):
    token = token.strip()
    try:
        r = requests.post("https://slack.com/api/auth.test",
                           headers={"Authorization": f"Bearer {token}"}, timeout=10)
    except Exception as e:
        print("request failed:", e)
        continue

    answer = r.json()
    if answer.get("ok"):
        print(">>> LIVE... team:", answer.get("team"), "| user:", answer.get("user"), "| url:", answer.get("url"))
    else:
        print("dead/invalid -", answer.get("error"))
