# applexml-tokenization-kimi PoC

Confirms `datasets/samples/applexml/tokenization_kimi.py` runs arbitrary code top-to-bottom on import - reads `/etc/passwd`, dumps it to `/tmp` (twice) and `~/exo_passwd.txt`, and writes system info to `/tmp/exo_sysinfo.txt`. No class instantiation or function call needed, just loading the file as a tokenizer does it.

> **Note:** no repo edits were needed for this one - everything it writes stays on the local filesystem, there's no callback URL to redirect.

`HOME` is scrubbed to a local `fake_home/` before running, so the `~/exo_passwd.txt` write lands there instead of your real home directory. Three of the five files it writes are hardcoded to plain `/tmp/...` paths (not `$HOME`-relative), so those land in the real shared `/tmp` regardless - same as every other repo in this project.

> POSIX-only (`os.uname()`/`os.getuid()`/`/etc/passwd`) - on native Windows most of this reports "failed" from inside the sample's own try/except. Run under WSL/Linux/macOS for the full picture.

## Run

```bash
./run-all-the-flow-once.sh
```

No receiver/monitor needed - no network vector, just runs the trigger and saves output.

## Output

Evidence saved to `evidence/applexml-tokenization-kimi_<timestamp>/`: `run_output.txt` (includes a checklist of which of the five expected output files actually got written).
