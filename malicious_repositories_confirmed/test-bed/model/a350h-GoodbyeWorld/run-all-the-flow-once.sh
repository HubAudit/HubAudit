#!/bin/bash
# usage: ./run-all-the-flow-once.sh

# Kill whatever's holding port 8080 from a previous run - not just this
# repo's own http.server. A receiver from ANY of these testbed repos can be
# left squatting on 8080 (e.g. a `nc -lkp 8080` from another repo, which
# never exits on its own because of -k) if that run's script was
# interrupted or never killed its own receiver at the end. Matching only
# "python3 -m http.server 8080" misses that - a request here would connect
# fine (TCP-wise) to that leftover nc and just hang forever waiting for an
# HTTP response nc will never send. fuser is tool-agnostic: kills whatever
# is actually bound to the port, regardless of what it is.
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 0.5

./receiver.sh > /tmp/receiver_output.txt 2>&1 &
sleep 1

./monitor.sh a350h-GoodbyeWorld &
sleep 2

python3 execute-poc.py 2>&1 | tee /tmp/run_output.txt

sleep 2
sudo fuser -k 8080/tcp 2>/dev/null || true
sudo pkill -INT -f "tcpdump -i lo"
sleep 1

OUT=$(cat evidence/.current_run)
sudo chown "$(id -u)":"$(id -g)" "$OUT/capture.pcap"
cp /tmp/run_output.txt "$OUT/run_output.txt"
cp /tmp/receiver_output.txt "$OUT/receiver_output.txt"

echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
echo
echo "=== what receiver.sh (http server) got ==="
cat "$OUT/receiver_output.txt"
