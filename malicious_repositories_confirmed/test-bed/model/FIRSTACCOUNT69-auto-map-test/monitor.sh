#!/bin/bash
# usage: ./monitor.sh <repo-name>
REPO=$1
# Reuse the folder receiver.sh already created for this run so capture.pcap
# lands next to receiver_output.txt instead of in its own timestamped dir.
if [ -s evidence/.current_run ]; then
    OUT=$(cat evidence/.current_run)
else
    OUT="evidence/${REPO}_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$OUT"

echo "capturing to $OUT/capture.pcap"
sudo tcpdump -i lo -w "$OUT/capture.pcap" "port 8080"