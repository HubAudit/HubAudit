# FIRSTACCOUNT69-auto-map-test PoC

This confirms `models/FIRSTACCOUNT69-auto-map-test/model.py` exfiltrates env/host data to `127.0.0.1:8080/log` on plain `import model` - no class instantiation needed.

> **Note:** the real payload target (`FIRSTACCOUNT69-ssrf-probe.hf.space`, commented out in `model.py`) was swapped for a local `127.0.0.1:8080` receiver for safety - nothing leaves the machine during this test.

## The Flow

For testing and evidence:
receiver → monitor → trigger → saves evidence

## Manual (3 terminals, in order)

1. **Receiver** - `./receiver.sh` (listens on 8080)
2. **Monitor** - `./monitor.sh FIRSTACCOUNT69-auto-map-test` (tcpdump capture, needs sudo)
3. **Execute-POC** - `python3 execute-poc.py`

Check terminal 1 for the captured POST. Stop monitor (`Ctrl-C`) then receiver when done.

## Run all the flow at once:

```bash
./run-all-the-flow-once.sh
```

## Output

Evidence saved to `evidence/FIRSTACCOUNT69-auto-map-test_<timestamp>/`: `capture.pcap`, `run_output.txt`, `receiver_output.txt`.

