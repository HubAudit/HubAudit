import pickle, base64
# Received from untrusted source
data = base64.b64decode("+844tmdXvAbcFhRie6T5SmXS6Ae5Mjx4BPouaiAX8RNZG0AQ8yXXVyQkM3UoSgBB5YVKpPVZ//BVe337")
obj = pickle.loads(data)  # VULNERABLE — arbitrary code execution via __reduce__
