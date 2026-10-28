#!/bin/bash
REPO=$1
OUT="evidence/${REPO}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "capturing to $OUT/capture.pcap"
sudo tcpdump -i lo -w "$OUT/capture.pcap" "port 8080"
