# Changes made for local testing

| File | Change | Why |
|---|---|---|
| `malicious/sample-0669.py` | C2 target changed from `("112.251.40.139", 9787)` (real external IP) to `("127.0.0.1", 8080)` | this is a raw reverse shell one-liner - connecting to the real hardcoded IP would mean opening an actual connection to unknown live infrastructure on the internet. Redirected to loopback so it only ever reaches our own local listener |
