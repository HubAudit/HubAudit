# torchsight-cybersecurity-classification-benchmark PoC

The `torchsight/cybersecurity-classification-benchmark` dataset flags 15 files -
3 families of 5 near-identical samples each (the benchmark's "malicious" class).
One script per family:

| Script | Family | Pattern | Runnable |
|---|---|---|---|
| [`poc_shell.py`](poc_shell.py) | `sample-0657,0661,0665,0669,0673.py` | reverse shell to a hardcoded C2 IP:port | yes - via `sample-0669` (see safety note) |
| [`poc_sqli.py`](poc_sqli.py) | `sample-0643,0646,0649,0652,0655.py` | f-string SQL query, no parameterization | yes - runs `sample-0643` in an in-memory db |
| [`poc_pickle.py`](poc_pickle.py) | `sample-0732,0734,0736,0738,0740.py` | `pickle.loads()` on untrusted bytes | runs the real sample; ends in `UnpicklingError` (see note) |

All 15 sample files are downloaded under `datasets/samples/torchsight-cybersecurity-classification-benchmark/malicious/`.

> **Reverse-shell safety:** only `sample-0669.py`'s C2 target was redirected to `127.0.0.1:8080` (see `datasets/samples/.../CHANGES.md`). The other four shell samples (`0657/0661/0665/0673`) **still point at real external C2 IPs** and are NOT run. `poc_shell.py` runs only `0669`, and additionally monkeypatches `socket.connect` to loopback as a safety net.

> **Pickle note:** `sample-0732.py`'s shipped base64 blob is a placeholder, not a real serialized pickle. Running the sample directly (`python3 .../malicious/sample-0732.py`) just errors out before any code runs:
>
> ```
> _pickle.UnpicklingError: invalid load key, '\xe5'.
> ```
>
> (the blob decodes to bytes whose first byte, `0xe5`, isn't a valid pickle opcode). `poc_pickle.py` runs this real sample, so **its expected output is exactly that `UnpicklingError`** - documenting that the sample as-shipped is inert. A working demonstration of the same `pickle.loads()` code-execution primitive (a crafted `__reduce__` gadget that prints `pwned via pickle.loads()`) is included at the bottom of `poc_pickle.py`, commented out - uncomment it to actually detonate the vector.

## Run

### All three at once (automated, saves evidence)

```bash
./run_all_at_once.sh
```

Clears port 8080 → `auto_receiver.sh` (scripted `nc`) + `monitor.sh` (tcpdump) → runs the three PoCs in sequence (`poc_shell.py`/0669, `poc_sqli.py`, `poc_pickle.py`) → saves `capture.pcap`, `run_shell.txt`, `run_sqli.txt`, `run_pickle.txt`, `receiver_output.txt` to `evidence/`.

### Individually

```bash
# reverse shell - interactive (drive the shell yourself)
./receiver.sh          # terminal 1 - nc -lvp 8080
python3 poc_shell.py   # terminal 2

python3 poc_sqli.py    # sqli - prints normal lookup then the ' OR '1'='1 injection
python3 poc_pickle.py  # pickle - runs the real sample; ends in UnpicklingError (placeholder blob)
```

## Output

Evidence from `./run_all_at_once.sh` lands in `evidence/torchsight-cybersecurity-classification-benchmark_<timestamp>/`: `capture.pcap`, `run_shell.txt`, `run_sqli.txt`, `run_pickle.txt`, `receiver_output.txt`.

> `run_shell.txt` is expected to be **empty** - `poc_shell.py` redirects its own stdout onto the socket (that's what the reverse shell does), so the shell's `id`/`pwd` output shows up in `receiver_output.txt` and `capture.pcap`, not in `run_shell.txt`.
>
> `run_pickle.txt` is expected to contain a **`_pickle.UnpicklingError`** traceback, not a success line - that's `poc_pickle.py` running the real (placeholder) sample. See the pickle note above.
