#!/bin/bash
# terminal 1: receiver - serves ./serve/helloworld.py at http://127.0.0.1:8080/helloworld.py
# run this first, leave it running
cd "$(dirname "$0")/serve"
python3 -m http.server 8080 --bind 127.0.0.1
