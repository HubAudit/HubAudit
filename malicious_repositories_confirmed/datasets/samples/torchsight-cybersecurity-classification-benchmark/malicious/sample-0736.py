import pickle, base64
# Received from untrusted source
data = base64.b64decode("qTJdNZenK4uh9XOsO7HrZwdDYArrOnuCdP+tyinwsPxSJOzeSsxb674BRK+AkxT9EWXgCkD/dkeqVgK+")
obj = pickle.loads(data)  # VULNERABLE — arbitrary code execution via __reduce__
