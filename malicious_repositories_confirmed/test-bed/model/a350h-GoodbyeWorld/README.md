# a350h-GoodbyeWorld PoC

This confirms `models/a350h-GoodbyeWorld/modeling.py` runs a base64-encoded `exec()` loader inside `ResnetModel.__init__` - fetches a URL and execs whatever comes back, triggered by plain `AutoModel.from_pretrained(..., trust_remote_code=True)`

> **Note:** the real payload URL (`https://raw.githubusercontent.com/ah73/HelloWorld/refs/heads/main/helloworld.py`, redirected in `modeling.py`) was swapped for a local `127.0.0.1:8080` testing safety - nothing leaves the machine during this test.

## Run

```bash
./run-all-the-flow-once.sh
```

Runs receiver → monitor → trigger → saves evidence automatically.

## Manual (3 terminals, in order)

```bash
# Terminal 1 - Receiver (serves serve/helloworld.py at http://127.0.0.1:8080/helloworld.py)
./receiver.sh

# Terminal 2 - Monitor (tcpdump capture, needs sudo)
./monitor.sh a350h-GoodbyeWorld

# Terminal 3 - Trigger
python3 execute-poc.py
```

Check terminal 1 for the fetched GET request. Stop monitor (`Ctrl-C`) then receiver when done.

## Output

Evidence saved to `evidence/a350h-GoodbyeWorld_<timestamp>/`: `capture.pcap`, `run_output.txt`, `receiver_output.txt`.

## Expected error after the payload runs

`model.safetensors` in `models/a350h-GoodbyeWorld/` was originally a Git LFS
pointer stub (134 bytes, not the real ~98MB file) - `git-lfs` was never
installed when this repo was cloned. That's fixed now: the real weights were
fetched straight from the HF `resolve` endpoint (`curl -sL -o
model.safetensors https://huggingface.co/a350h/GoodbyeWorld/resolve/main/model.safetensors`,
no `git-lfs` binary needed) and loading now completes (`Loading weights: 100%|...|332/332`).

`run_output.txt` still ends in a traceback, but a different one now - also
expected, not a failed PoC:

```
CustomClass has been instantiated!
Remote code loaded and executed (in-memory).
Loading weights: 100%|██████████| 332/332 [00:00<00:00, 4841.93it/s]
Traceback (most recent call last):
  ...
  File ".../modeling_utils.py", line 4864, in _move_missing_keys_from_meta_to_device
    for key in missing_keys - self.all_tied_weights_keys.keys():
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'ResnetModel' object has no attribute 'all_tied_weights_keys'. Did you mean: '_tied_weights_keys'?
```

The first three lines are the payload executing and the real weights loading
successfully - `trust_remote_code=True` already imported `modeling.py` and
instantiated `ResnetModel` (running the base64 `exec()` loader), and all 332
tensors loaded from the real safetensors file. The `AttributeError` happens
strictly afterward, inside `transformers`' own `_finalize_model_loading` -
not in `modeling.py` or `configuration_resnet.py` (neither references
`all_tied_weights_keys` or `_tied_weights_keys` at all). Root cause:
`config.json` pins `"transformers_version": "4.53.2"`, but this venv has
`transformers==5.14.1` installed - an internal attribute this model class
relies on evidently changed across that major-version jump. A library
version-compatibility bug, unrelated to the exploit and not something this
testbed modified.

This is still an instance of the documented load-time risk above - code
execution / file access on load of a malicious model, dataset, config, or
pickle. The risk is realized at `trust_remote_code` import/instantiation
time, before any weights are ever read, and both the exec and the full
weight load already completed by the time this error shows up.
