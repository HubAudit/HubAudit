# UCSC-VLAA-ip-info PoC

This confirms `ip-info-apikey-exfil-py/ip-info.py` starts a background thread on run that reads `~/.openclaw/agents/main/agent/auth-profiles.json` (if present) and POSTs it out - alongside its stated purpose of a legitimate IP-lookup call to `ipinfo.io`.

> **Note:** the exfil POST target was already redirected to a local `127.0.0.1:8080` receiver in the real sample - nothing related to the exfil vector leaves the machine during this test. The IP-lookup call to `https://ipinfo.io/json` is a real external request either way - it's the script's stated legitimate function, not part of the attack.

`execute-poc.py` - subprocess + full env scrub, plants the canary under a local `fake_home/`.

## Run

```bash
./run-all-the-flow-once.sh
```

Runs receiver → monitor → the PoC → saves evidence automatically.

## Manual (3 terminals, in order)

```bash
# Terminal 1 - Receiver (listens on 8080)
./receiver.sh

# Terminal 2 - Monitor (tcpdump capture, needs sudo)
./monitor.sh UCSC-VLAA-ip-info

# Terminal 3 - Execute PoC
python3 execute-poc.py
```

Check terminal 1 for the captured POST. Stop monitor (`Ctrl-C`) then receiver when done.

## Output

Evidence saved to `evidence/UCSC-VLAA-ip-info_<timestamp>/`: `capture.pcap`, `run_output.txt`, `receiver_output.txt`.
