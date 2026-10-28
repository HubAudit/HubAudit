# Sample file - triggers bandit, semgrep, opengrep
import subprocess
import os

# bandit: hardcoded password (B105)
password = "supersecret123"

# bandit: shell=True subprocess (B602)
def run_cmd(user_input):
    subprocess.call(user_input, shell=True)

# bandit + semgrep: eval on user input (B307)
def evaluate(expr):
    return eval(expr)

# bandit: os.system (B605)
def execute(cmd):
    os.system(cmd)
