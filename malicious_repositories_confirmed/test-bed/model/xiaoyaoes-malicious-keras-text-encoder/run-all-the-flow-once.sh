#!/bin/bash
# usage: ./run-all-the-flow-once.sh
# no network vector here (unlike the other repos) - this one writes a local
# file on load, so no receiver/monitor needed, just run + capture output.

mkdir -p evidence
OUT="evidence/xiaoyaoes-malicious-keras-text-encoder_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"

python3 execute-poc.py 2>&1 | tee "$OUT/run_output.txt"

echo
echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
