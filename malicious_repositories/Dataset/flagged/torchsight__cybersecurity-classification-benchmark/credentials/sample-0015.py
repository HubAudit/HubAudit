import requests
SLACK_BOT_TOKEN = "xoxb-7620395-7653241355-6Iyq3CltV0t2Qi/ORNVZGJ1o"
SLACK_SIGNING_SECRET = "beef8cd95fc8086e5f395bd1376f2858"
def post_message(channel, text):
    requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text})
