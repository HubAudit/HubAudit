import pickle, base64
# Received from untrusted source
data = base64.b64decode("xcP4c/9MDc3ms08mgk0jA0cVYqhJxU9q/hdkihEz3WRkE+SUUfAQ1QFNEotXcWz6EqUmKi4H/DP3LDzr")
obj = pickle.loads(data)  # VULNERABLE — arbitrary code execution via __reduce__
