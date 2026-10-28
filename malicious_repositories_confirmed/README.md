# Overview

This is the testbed where we verified malicious and vulnerable Hugging Face models and datasets. We demonstrated that Python scripts can be effectively used to cause system‑level malicious impact, and all it takes is for an attacker to similarly manipulate these files on a target machine. Given these existing possibilities, script scanning on Hugging Face should be increasingly vetted to elevate trust, in other words, python script files should be reviewed more thoroughly across the platform.


## `datasets/`

Sample data pulled from Hugging Face dataset repos that catalog malicious
agent skills and attack techniques - e.g. `samples/zhmzm` and
`samples/XuWY__AgentTrap` (the `AgentTrap` benchmark's flagged "skills",
covering prompt injection, patch injection, OAuth/IAM exfil, and more),
`samples/inclusionAI-A3S-Bench` (malicious file-management skills), and a
few smaller single-technique samples (`applexml`, `UCSC-VLAA`,
`torchsight-cybersecurity-classification-benchmark`). This is reference
data the PoCs in `test-bed/datasets/` load and run against directly - none
of it has been altered from what was downloaded.

## `models/`

Full clones of Hugging Face model repos that ship malicious
`trust_remote_code=True` code or unsafe deserialization vectors - e.g.
`a350h-GoodbyeWorld` (a base64 `exec()` dropper in `modeling.py`) and
`scthornton-bert-tiny-multi-attack-demo` (a pickle RCE payload alongside a
data-exfil vector). Each repo's own `CHANGES.md` documents the one edit made
to it: redirecting its hardcoded callback URL to `127.0.0.1` so triggering
it doesn't call out to a real, live, mutable endpoint. No other logic was
changed.

## `test-bed/`

- **Structure:** One folder per repository inside `test-bed/model/` or `test-bed/datasets/`.
- **Execution:** `execute-poc-*.py` scripts load the flagged file.
- **Automation:** Scripts like `receiver.sh`, `monitor.sh`, and `run-all-the-flow-once.sh` handle local setup, traffic capture (`tcpdump`), and evidence collection.
- **Evidence:** Saved to each folder's `evidence/` directory (`capture.pcap`, run logs, receiver output).
- **Environment:** Shared virtual environment (`test-bed/venv/`) managed by a common `requirements.txt`.
- **Documentation:** Each subfolder contains a `README.md` with instructions and expected outcomes.


## Test environment

All PoCs were verified on this machine. Behaviour can differ elsewhere - the
platform-specific notes (Windows-only vectors, GUI/keyboard requirements, no
PowerShell, etc.) in individual repo READMEs are relative to this setup.

| | |
|---|---|
| OS | Debian GNU/Linux 12 (bookworm) |
| Kernel | Linux 6.1.0-52-cloud-amd64 |
| Architecture | x86_64 |
| Machine | headless cloud VM (no GUI/display), 4 vCPU, 31 GiB RAM |
| GPU | none - CPU-only |
| Python | 3.11.2 (project venv at `test-bed/venv/`) |
