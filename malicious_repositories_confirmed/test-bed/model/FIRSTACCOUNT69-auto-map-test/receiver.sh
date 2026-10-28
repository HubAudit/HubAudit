# #!/bin/bash
# # terminal 1: receiver - run this first, leave it running
# nc -lkp 8080



#!/bin/bash
# receiver.sh - Run this first in Terminal 1
# This sets up the listener, displays output, and saves it directly to the evidence folder.
REPO=$1
OUT="evidence/${REPO}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
# Record the folder for this run so monitor.sh (and run-all-the-flow-once.sh) write into the
# same evidence dir instead of computing their own, later timestamp.
echo "$OUT" > evidence/.current_run

# echo "Saving receiver output to $OUT/receiver_output.txt"
nc -lkp 8080 | tee "$OUT/receiver_output.txt"