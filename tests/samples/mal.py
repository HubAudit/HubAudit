from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route("/")
def run():
    cmd = request.args.get("cmd")  # remote input
    subprocess.call(cmd, shell=True)  # dangerous sink
    return "done"

if __name__ == "__main__":
    app.run()