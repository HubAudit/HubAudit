import requests
SLACK_BOT_TOKEN = "xoxb-2889074-1526928976-cHM+tBiAyXQXlbTIJ4YobIA9"
SLACK_SIGNING_SECRET = "2a120ddd58b0da30382bdb5c84d577ce"
def post_message(channel, text):
    requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text})
