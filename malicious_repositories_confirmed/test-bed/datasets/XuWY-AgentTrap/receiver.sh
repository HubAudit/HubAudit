#!/bin/bash
# terminal 1: receiver - serves ./serve/{next,data.csv} for case 0014's GET
# requests; any POST (0014's final submit, 0026, 0039) gets a real (if
# unimplemented, 501) HTTP response instead of hanging - same class of issue
# as GoodbyeWorld's dropper. Covers all three network-vector cases (0014,
# 0026, 0039) with one receiver.
cd "$(dirname "$0")/serve"
python3 -m http.server 8080 --bind 127.0.0.1
