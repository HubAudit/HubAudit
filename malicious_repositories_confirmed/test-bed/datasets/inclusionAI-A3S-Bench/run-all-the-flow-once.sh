#!/bin/bash
# usage: ./run-all-the-flow-once.sh
set -euo pipefail

REPO="inclusionAI-A3S-Bench"

echo "[1] clearing any stale listener on 8080"
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 1

./receiver.sh > /tmp/receiver_output.txt 2>&1 &
sleep 1

./monitor.sh "$REPO" > /tmp/monitor_output.txt 2>&1 &
sleep 2

echo "[2] execute-poc-backdoor.py - utils.py telemetry + persistence threads"
python3 execute-poc-backdoor.py > /tmp/backdoor_output.txt 2>&1

echo "[3] execute-poc-utils.py - same utils.py vector, lighter scratch-home setup"
python3 execute-poc-utils.py > /tmp/utils_output.txt 2>&1

echo "[4] execute-poc-organize.py - organize.py background_sync exfil"
python3 execute-poc-organize.py > /tmp/organize_output.txt 2>&1

echo "[5] execute-poc-traversal.py - calculate_hash() path traversal (no network)"
python3 execute-poc-traversal.py > /tmp/traversal_output.txt 2>&1

sleep 2
sudo pkill -INT -f "tcpdump -i lo" 2>/dev/null || true
sudo pkill -f "nc -lkp 8080" 2>/dev/null || true
sleep 1

OUT=$(cat evidence/.current_run)
sudo chown "$(id -u)":"$(id -g)" "$OUT/capture.pcap"
cp /tmp/backdoor_output.txt "$OUT/backdoor_output.txt"
cp /tmp/utils_output.txt "$OUT/utils_output.txt"
cp /tmp/organize_output.txt "$OUT/organize_output.txt"
cp /tmp/traversal_output.txt "$OUT/traversal_output.txt"
cp /tmp/receiver_output.txt "$OUT/receiver_output.txt"
cp /tmp/monitor_output.txt "$OUT/monitor_output.txt"

echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
echo
echo "=== receiver output ==="
cat /tmp/receiver_output.txt
