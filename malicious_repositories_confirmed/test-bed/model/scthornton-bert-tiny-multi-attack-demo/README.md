# scthornton-bert-tiny-multi-attack-demo PoC

Confirms two separate vectors in `models/scthornton-bert-tiny-multi-attack-demo`:
- **exfil** - `train.py`'s `exfiltrate_data()` POSTs training data to a remote URL
- **pickle** - `malicious_optimizer_state.pkl` carries an opcode payload (disassembled only here, never executed)

> **Note:** the real exfil URL was redirected to a local `127.0.0.1:8080` receiver for safety - nothing leaves the machine during this test.

## Run

```bash
./run-all-the-flow-once.sh
```

Runs receiver → monitor → both triggers → saves evidence automatically.

## Manual (3 terminals, in order)

```bash
# Terminal 1 - Receiver (listens on 8080)
./receiver.sh

# Terminal 2 - Monitor (tcpdump capture, needs sudo)
./monitor.sh scthornton-bert-tiny-multi-attack-demo

# Terminal 3 - Triggers
python3 execute-poc-exfil.py
python3 execute-poc-pickle.py
```

Check terminal 1 for the captured POST. Stop monitor (`Ctrl-C`) then receiver when done.

## Output

Evidence saved to `evidence/scthornton-bert-tiny-multi-attack-demo_<timestamp>/`: `capture.pcap`, `exfil_output.txt`, `pickle_output.txt`, `receiver_output.txt`.
