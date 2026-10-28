import os
import requests

tokens = ["TELEGRAM_TOKEN_HERE"]
for i, token in enumerate(tokens, 1):
    token = token.strip()
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    except Exception as e:
        print("request failed:", e)
        continue

    print("status:", r.status_code)
    answer = r.json()
    if answer.get("ok"):
        bot = answer.get("result") or {}
        print(">>> LIVE .... id:", bot.get("id"), "| name:", bot.get("first_name"), "| @" + str(bot.get("username")))
    else:
        print("dead/invalid -", answer.get("description"))
