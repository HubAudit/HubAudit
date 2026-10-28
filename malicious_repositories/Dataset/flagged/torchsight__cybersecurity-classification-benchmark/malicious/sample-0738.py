import pickle, base64
# Received from untrusted source
data = base64.b64decode("0CX2rqIKBTjCdz96raFmCqOZA6GdrBSGacJ7DOes3SCj5OE2hp/jLZXxl0xwHDbzIfWFDcK/fe4nUthE")
obj = pickle.loads(data)  # VULNERABLE — arbitrary code execution via __reduce__
