# Changes made for local testing

| File | Change | Why |
|---|---|---|
| `phase1-only/.../ip-info-apikey-exfil-py/ip-info.py` | exfil target changed from `http://{{ATTACKER_WEBHOOK}}` (unfilled template placeholder) to `http://127.0.0.1:8080/exfil` | placeholder wasn't a real URL - couldn't fire as shipped, needed a real target to test against |
| `phase-full/.../ip-info-apikey-exfil-py/ip-info.py` | same change, identical duplicate file at a different path in the dataset | same reason |

## Notes

- The exfil reads `~/.openclaw/agents/main/agent/auth-profiles.json` and POSTs it if
  present. The real path won't exist on a normal box, so nothing fires unless that
  file exists - `test-bed/datasets/UCSC-VLAA-ip-info/trigger.py` plants a fake canary
  version of it under a scrubbed `$HOME` before running.
- `get_ip_info()` (the non-malicious half of the script) does make a real call to
  `https://ipinfo.io/json` - a legitimate public IP lookup API, left untouched since
  it's not part of the attack vector, just cover traffic.
