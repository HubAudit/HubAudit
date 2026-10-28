# inclusionAI-A3S-Bench PoC

Confirms four separate vectors across two flagged skill scripts in `inclusionAI-A3S-Bench`'s `File_Management` malicious skills:

- **backdoor** (`russellfei_file-manager/scripts/utils.py`) - importing the module alone starts two daemon threads: one POSTs credential-shaped files (`~/.ssh/id_rsa`, `~/.openclaw/*`, `~/.aws/credentials`) out, the other appends a `curl | bash` line to `~/.bashrc` for persistence
- **organize** (`1999azzar_file-organizer-skill/scripts/organize.py`) - `_background_sync()` reads the same set of credential-shaped files plus `/proc/self/environ` and POSTs them out, triggered just by running the CLI (even with `--dry-run`)
- **traversal** (`utils.calculate_hash()`) - no containment check on the path it's given, so a caller scoped to one directory can still be pointed outside it via `../`

> **Note:** both payloads' real callback targets were redirected to a local `127.0.0.1:8080` receiver for safety - nothing leaves the machine during this test. `organize.py`'s telemetry URL was a real external hostname before this pass.

## Run

```bash
./run-all-the-flow-once.sh
```

Clears any stale port-8080 listener, then runs receiver → monitor → all four PoCs (`execute-poc-backdoor.py`, `execute-poc-utils.py`, `execute-poc-organize.py`, `execute-poc-traversal.py`) → stops capture → saves evidence automatically.

## Manual

```bash
# Terminal 1 - Receiver (listens on 8080)
./receiver.sh

# Terminal 2 - Monitor (tcpdump capture, needs sudo)
./monitor.sh inclusionAI-A3S-Bench

# Terminal 3 - Run whichever PoC(s) you want
python3 execute-poc-backdoor.py
python3 execute-poc-utils.py
python3 execute-poc-organize.py
python3 execute-poc-traversal.py
```

`execute-poc-traversal.py` has no network component - it's a local-only proof, nothing to see on the receiver for that one.

## Output

Evidence saved to `evidence/inclusionAI-A3S-Bench_<timestamp>/`: `capture.pcap`, `backdoor_output.txt`, `utils_output.txt`, `organize_output.txt`, `traversal_output.txt`, `receiver_output.txt`, `monitor_output.txt`.
