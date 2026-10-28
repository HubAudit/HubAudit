# xitro-rce-trust-remote-code PoC

Confirms `models/xitro-rce-trust-remote-code`'s `modeling_custom.py`/`tokenization_custom.py` exfiltrate env/host data on `trust_remote_code=True`

> **Note:** the real exfil target (`https://xitro-env-probe.hf.space/exfil`, redirected in the repo's own files) was swapped for a local `127.0.0.1:8080` receiver for safety - nothing leaves the machine during this test.


## Run

```bash
./run-all-the-flow-once.sh
```

Runs receiver → monitor → trigger → saves evidence automatically.

## Manual (3 terminals, in order)

```bash
# Terminal 1 - Receiver (listens on 8080)
./receiver.sh

# Terminal 2 - Monitor (tcpdump capture, needs sudo)
./monitor.sh xitro-rce-trust-remote-code

# Terminal 3 - Execute PoC
python3 execute-poc.py
```

Check terminal 1 for the captured POST. Stop monitor (`Ctrl-C`) then receiver when done.

## Output

Evidence saved to `evidence/xitro-rce-trust-remote-code_<timestamp>/`: `capture.pcap`, `run_output.txt`, `receiver_output.txt`.
