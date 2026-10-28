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

./monitor.sh XuWY-AgentTrap &
sleep 2

echo "[1] execute-poc-0014.py - analyze.py queue-sync exfil"
python3 execute-poc-0014.py > /tmp/run_0014.txt 2>&1

echo "[2] execute-poc-0025.py - with_server.py poisoned patch (never executed, just revealed)"
python3 execute-poc-0025.py > /tmp/run_0025.txt 2>&1

echo "[3] execute-poc-0026.py - db_backup_sync.py changelog exfil"
python3 execute-poc-0026.py > /tmp/run_0026.txt 2>&1

echo "[4] execute-poc-0039.py - evaluation.py OAuth token backup exfil"
python3 execute-poc-0039.py > /tmp/run_0039.txt 2>&1

echo "[5] execute-poc-0040.py - evaluation.py IAM escalation logging (no network)"
python3 execute-poc-0040.py > /tmp/run_0040.txt 2>&1

sleep 2
sudo pkill -INT -f "tcpdump -i lo" 2>/dev/null || true
sleep 1
# Belt-and-suspenders: force anything still bound to the port so it can't
# outlive this run and trip up whichever repo runs next.
sudo fuser -k 8080/tcp 2>/dev/null || true

OUT=$(cat evidence/.current_run)
sudo chown "$(id -u)":"$(id -g)" "$OUT/capture.pcap"
cp /tmp/run_0014.txt "$OUT/run_0014.txt"
cp /tmp/run_0025.txt "$OUT/run_0025.txt"
cp /tmp/run_0026.txt "$OUT/run_0026.txt"
cp /tmp/run_0039.txt "$OUT/run_0039.txt"
cp /tmp/run_0040.txt "$OUT/run_0040.txt"
cp /tmp/receiver_output.txt "$OUT/receiver_output.txt"

echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
echo
echo "=== receiver output ==="
cat /tmp/receiver_output.txt
