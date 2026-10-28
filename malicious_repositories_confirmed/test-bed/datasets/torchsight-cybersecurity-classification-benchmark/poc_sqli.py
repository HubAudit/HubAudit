# PoC — runs the actual flagged sample-0643.py from the dataset
# (representative of sample-0643/0646/0649/0652/0655.py, all identical).
# No extra deps (sqlite3 stdlib).
# get_user() builds its SQL with an f-string -- any username string
# controls the WHERE clause.
#
# The guard below is just a safety net in case the sample dir is incomplete -
# sample-0643.py is normally present alongside the other 14 flagged files.

import os
import runpy
import sqlite3

flagged = os.path.expanduser(
    "~/repos/datasets/samples/torchsight-cybersecurity-classification-benchmark/"
    "malicious/sample-0643.py"
)

if not os.path.exists(flagged):
    raise SystemExit(
        f"sample not present: {flagged}\n"
        "Only sample-0669.py (reverse-shell family) is downloaded in this testbed - "
        "the sqli family was left un-fetched. See README."
    )

conn = sqlite3.connect(":memory:")
cursor = conn.cursor()
cursor.execute("CREATE TABLE users (username TEXT, role TEXT)")
cursor.executemany("INSERT INTO users VALUES (?, ?)", [("alice", "user"), ("admin", "admin")])
conn.commit()

mod = runpy.run_path(flagged, init_globals={"cursor": cursor})

print("get_user('alice'):        ", mod["get_user"]("alice"))
print("get_user(\"' OR '1'='1\"):", mod["get_user"]("' OR '1'='1"))  # <- the trigger
