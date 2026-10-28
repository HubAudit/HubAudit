#!/bin/bash

#
# UNLIKE the others, this one has no localhost redirect and no
# receiver/monitor step - there's no callback URL to intercept, the danger is
# gpt-4o genuinely deciding to run `subprocess.run(cmd, shell=True)` and
# `os.remove(path)` against THIS machine. Only run this in a disposable
# VM/container you don't mind losing files in.


mkdir -p evidence
OUT="evidence/airblackbox-eu-ai-act-compliance-benchmark_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"

python3 execute-poc.py 2>&1 | tee "$OUT/run_output.txt"

echo
echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
