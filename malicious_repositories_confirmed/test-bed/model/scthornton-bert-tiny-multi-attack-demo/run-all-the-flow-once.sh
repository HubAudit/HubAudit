#!/bin/bash
# usage: ./run-all-the-flow-once.sh

sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 1

./receiver.sh > /tmp/receiver_output.txt 2>&1 &
sleep 1

./monitor.sh scthornton-bert-tiny-multi-attack-demo &
sleep 2

python3 execute-poc-exfil.py 2>&1 | tee /tmp/exfil_output.txt
python3 execute-poc-pickle.py 2>&1 | tee /tmp/pickle_output.txt

sleep 2
sudo pkill -INT -f "tcpdump -i lo"
sleep 1
# nc -lkp never exits on its own (-k keeps it listening forever) - kill it
# now, not just at the start of the next run, so it can't answer (or just
# silently swallow) another repo's request in the meantime.
sudo fuser -k 8080/tcp 2>/dev/null || true

OUT=$(cat evidence/.current_run)
sudo chown "$(id -u)":"$(id -g)" "$OUT/capture.pcap"
cp /tmp/exfil_output.txt "$OUT/exfil_output.txt"
cp /tmp/pickle_output.txt "$OUT/pickle_output.txt"
cp /tmp/receiver_output.txt "$OUT/receiver_output.txt"

echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
echo
echo "=== what receiver.sh got ==="
cat /tmp/receiver_output.txt
