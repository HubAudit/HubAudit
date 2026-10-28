# XuWY-AgentTrap PoC

Five cases, each a small script that loads the real flagged file and triggers its hidden behavior. `connections.py` is a shared stub for a local module cases 0039/0040 need but wasn't staged in this dataset (0039 also has a *real* one next to `evaluation.py`, but it imports the `mcp` package which isn't installed here - our stub wins priority on `sys.path` to sidestep that).

| Script | Flagged file | Trigger |
|---|---|---|
| [`execute-poc-0014.py`](execute-poc-0014.py) | `skills/malicious/case_0014_v3_dim5_data_analysis_parasitic/scripts/analyze.py` | `_sync_queue()` — polls `$ANALYSIS_QUEUE_NEXT_URL`, POSTs computed metrics out |
| [`execute-poc-0025.py`](execute-poc-0025.py) | `skills/malicious/case_0025_v3_dim9_webapp_testing_patch_inject/scripts/with_server.py` | `_generate_patch(i, ...)` for `i` 1-6 — index 5 returns a `curl \| bash` backdoor disguised as a fix (revealed only, never executed/applied) |
| [`execute-poc-0026.py`](execute-poc-0026.py) | `skills/malicious/case_0026_v3_dim9_changelog_db_sync/scripts/db_backup_sync.py` | `main()` — POSTs git log/cwd/user/hostname to `$CHANGELOG_SYNC_URL` |
| [`execute-poc-0039.py`](execute-poc-0039.py) | `skills/malicious/case_0039_v3_dim14_mcp_builder_oauth_exfil/scripts/evaluation.py` | import-time — ships `$OAUTH_REFRESH_TOKEN` to `$OAUTH_BACKUP_HOST` |
| [`execute-poc-0040.py`](execute-poc-0040.py) | `case_0040_v3_dim15_mcp_builder_iam_escalation/scripts/evaluation.py` (note: sits one level higher in the real tree, not under `skills/malicious/`) | import-time — logs `AdministratorAccess` IAM calls it's ready to issue |

> **Note:** all target URLs are read from environment variables by the flagged files themselves (`$ANALYSIS_QUEUE_NEXT_URL`, `$CHANGELOG_SYNC_URL`, `$OAUTH_BACKUP_HOST`) - no source edits were needed, each PoC just sets them to `127.0.0.1:8080` before running. Nothing leaves the machine during this test.

Scanner note: on 0039/0040, opengrep's only finding is an unrelated XXE warning on `ET.parse()` — the actual payload a few lines above it tripped no rule at all.

See [`../zhmzm-AgentTrap/`](../zhmzm-AgentTrap/) for the one case (prompt injection) that repo has and this one doesn't — its other 5 cases are byte-identical to these.

## Run

```bash
./run-all-the-flow-once.sh
```

Runs receiver (`http.server`, not `nc` - 0014 needs real GET responses for its queue-poll/data-fetch flow, and `http.server` answers any POST with a real 501 instead of hanging, covering 0026/0039 too) → monitor → all five PoCs in sequence → stop capture → evidence saved.

## Manual

```bash
pip install pandas anthropic
./receiver.sh                    # terminal 1
./monitor.sh XuWY-AgentTrap     # terminal 2
python3 execute-poc-0014.py      # terminal 3
python3 execute-poc-0025.py
python3 execute-poc-0026.py
python3 execute-poc-0039.py
python3 execute-poc-0040.py
```

`execute-poc-0025.py` and `execute-poc-0040.py` have no network component - nothing to see on the receiver for those two.

## Output

Evidence saved to `evidence/XuWY-AgentTrap_<timestamp>/`: `capture.pcap`, `run_0014.txt`, `run_0025.txt`, `run_0026.txt`, `run_0039.txt`, `run_0040.txt`, `receiver_output.txt`.
