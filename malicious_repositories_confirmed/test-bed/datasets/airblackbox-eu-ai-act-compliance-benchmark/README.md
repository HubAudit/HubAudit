# airblackbox-eu-ai-act-compliance-benchmark PoC

Confirms `samples/no_risk_levels_agent.py` wires `execute_shell` (arbitrary `subprocess.run(..., shell=True)`) and `delete_file` (`os.remove`) into a LangChain agent with **no risk classification** - `gpt-4o` can call either tool freely, with zero guardrails, based on nothing but the prompt.

> **This is not a safe, localhost-contained PoC like the other testbed repos.** There's no callback URL to redirect - the payload *is* a real LLM making real decisions. Running it makes genuine `gpt-4o` calls that can actually run shell commands and delete files **on whatever machine you run it on**. Only run this in a disposable VM/container.

## Run

```bash
export OPENAI_API_KEY=sk-...
./run-all-the-flow-once.sh
```

No receiver/monitor step - there's no network callback to capture, the risk is local shell/file access, not exfiltration.

## Manual

```bash
export OPENAI_API_KEY=sk-...
python3 execute-poc.py
```

## Output

Evidence saved to `evidence/airblackbox-eu-ai-act-compliance-benchmark_<timestamp>/`: `run_output.txt` (the agent's tool calls and results - review this before assuming anything was actually deleted).

## If you forgot to set `OPENAI_API_KEY`

```
openai.OpenAIError: Missing credentials. Please pass an `api_key`, `workload_identity`,
`admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` environment variable.
```

This means exactly what it says - `ChatOpenAI(model="gpt-4o")` can't construct an
OpenAI client without a real key, so the script fails before the agent ever runs (no
tool calls happen, nothing gets deleted, `run_output.txt` will just contain this
traceback). Unlike every other repo in this testbed, there's no fake/canary
credential that works here - the whole point of this PoC is a *genuine* `gpt-4o` call
deciding whether to run `execute_shell`/`delete_file`, so it needs a real,
working `OPENAI_API_KEY` to demonstrate anything at all. Export one and re-run - but
re-read the warning above first, since a real key means real tool calls.
