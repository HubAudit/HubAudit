import requests
SLACK_BOT_TOKEN = "xoxb-3149319-7785940292-Mvqiszuue3VhU+dm4FeT4E9h"
SLACK_SIGNING_SECRET = "cd3a1559868c5360ee252525b182adcf"
def post_message(channel, text):
    requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text})
