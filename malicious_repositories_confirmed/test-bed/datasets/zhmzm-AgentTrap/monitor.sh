#!/bin/bash
# usage: ./monitor.sh <repo-name>
REPO=$1
OUT="evidence/${REPO}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
# Record the folder for this run so run-all-the-flow-once.sh writes into the
# same evidence dir instead of guessing via `ls -t`.
echo "$OUT" > evidence/.current_run

echo "capturing to $OUT/capture.pcap"
# port 8080: shared receiver for 0014/0026/0039. port 8000: case_0007's
# stand-in dev server, hit by the hidden playwright navigation.
sudo tcpdump -i lo -w "$OUT/capture.pcap" "port 8080 or port 8000"
