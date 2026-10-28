#!/bin/bash
# scripted/automated use for run_all_at_once.sh - sends a couple harmless commands once the
# reverse shell connects, then exits, instead of needing a human to type into it
(sleep 1; echo "id"; sleep 1; echo "pwd"; sleep 1; echo "exit") | nc -lvp 8080
