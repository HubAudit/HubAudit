#!/bin/bash
# usage: ./run-all-the-flow-once.sh
# no network vector here - just run + capture output.

mkdir -p evidence
OUT="evidence/applexml-tokenization-kimi_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"

python3 execute-poc.py 2>&1 | tee "$OUT/run_output.txt"

echo
echo "=== evidence dir: $OUT ==="
ls -la "$OUT"
