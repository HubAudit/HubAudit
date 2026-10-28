# PoC — runs the actual flagged sample-0669.py from the dataset
# (representative of sample-0657/0661/0665/0669/0673.py, all identical - only
# 0669 is downloaded locally, see README).
# No extra deps. POSIX only (/bin/sh) -- won't work on native Windows.
#
# Real code connects to a hardcoded C2 IP then execs /bin/sh -i over the
# socket. In the sample dir, that IP is already redirected to 127.0.0.1:8080
# (see datasets/samples/.../CHANGES.md); the monkeypatch below is belt-and-
# suspenders so this still hits the local receiver even if pointed at a
# non-redirected sample.
#
# This runs the shell in-process (runpy), which redirects this process's own
# stdio over the socket. To catch it manually, in another terminal:
#   nc -lvp 8080
# Or run `./run_all_at_once.sh`, which wires up the receiver + tcpdump and runs all three
# PoCs (this one included) with evidence capture.
import os
import socket
import runpy

real_connect = socket.socket.connect
socket.socket.connect = lambda self, addr: real_connect(self, ("127.0.0.1", 8080))

flagged = os.path.expanduser(
    "~/repos/datasets/samples/torchsight-cybersecurity-classification-benchmark/"
    "malicious/sample-0669.py"
)
runpy.run_path(flagged, run_name="__main__")  # <- connects to 127.0.0.1:8080, spawns /bin/sh -i over it
