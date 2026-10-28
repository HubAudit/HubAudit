import pickle, base64
# Received from untrusted source
data = base64.b64decode("KeWC9r+pwhsY2SlQFVcKAN+61bExqw4JcEK+QkAcMhAYBgllm+j0WdzsXUlmM9RUHfQCBRAGXMlpAX6R")
obj = pickle.loads(data)  # VULNERABLE — arbitrary code execution via __reduce__
