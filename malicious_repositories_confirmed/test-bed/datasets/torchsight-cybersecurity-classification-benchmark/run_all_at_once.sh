#!/bin/bash
# usage: ./run_all_at_once.sh
# Runs all three malicious families in one go, each via its own poc_*.py, and
# saves evidence:
#   1. reverse shell  - poc_shell.py runs sample-0669.py (C2 redirected to
#      127.0.0.1:8080); auto_receiver.sh catches it and feeds id/pwd/exit;
#      monitor.sh captures the traffic to capture.pcap
#   2. sqli           - poc_sqli.py runs sample-0643.py against an in-memory db
#   3. pickle         - poc_pickle.py runs the real sample-0732.py, which ends
#                       in _pickle.UnpicklingError (its shipped blob is a
#                       non-decoding placeholder) - that error IS the expected
#                       output. A working gadget demo is commented out inside
#                       poc_pickle.py.
#
# Only the 0669 reverse shell has a network component. The other shell-family
# samples (0657/0661/0665/0673) still point at REAL external C2 IPs and are NOT
# run here - only 0669 was redirected to loopback.
#
# For a real interactive shell session instead, run receiver.sh yourself and
# then `python3 poc_shell.py` in another terminal.

# Clear anything left holding 8080 from a previous/interrupted run (nc -lvp
# keeps listening; tool-agnostic kill so it doesn't matter what it is).
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 1

./auto_receiver.sh > /tmp/receiver_output.txt 2>&1 &
sleep 1

./monitor.sh torchsight-cybersecurity-classification-benchmark &
sleep 2

echo "[1/3] reverse shell - poc_shell.py (sample-0669, C2 -> 127.0.0.1:8080)"
python3 poc_shell.py 2>&1 | tee /tmp/run_shell.txt

echo
echo "[2/3] sqli - poc_sqli.py (sample-0643)"
python3 poc_sqli.py 2>&1 | tee /tmp/run_sqli.txt

echo
echo "[3/3] pickle - poc_pickle.py (runs real sample-0732.py; expected: UnpicklingError)"
python3 poc_pickle.py 2>&1 | tee /tmp/run_pickle.txt

sleep 2
sudo pkill -INT -f "tcpdump -i lo"
sleep 1
sudo fuser -k 8080/tcp 2>/dev/null || true

LATEST=$(ls -t evidence/ | head -1)
sudo chown "$(id -u)":"$(id -g)" "evidence/$LATEST/capture.pcap"
cp /tmp/run_shell.txt  "evidence/$LATEST/run_shell.txt"
cp /tmp/run_sqli.txt   "evidence/$LATEST/run_sqli.txt"
cp /tmp/run_pickle.txt "evidence/$LATEST/run_pickle.txt"
cp /tmp/receiver_output.txt "evidence/$LATEST/receiver_output.txt"

echo
echo "=== evidence dir: evidence/$LATEST ==="
ls -la "evidence/$LATEST"
echo
echo "=== what the reverse shell returned (receiver) ==="
cat /tmp/receiver_output.txt
