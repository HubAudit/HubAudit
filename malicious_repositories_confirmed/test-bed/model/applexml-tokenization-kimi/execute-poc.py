import os
import subprocess

SCRIPT = os.path.expanduser(
    "~/repos/models/applexml/tokenization_kimi.py"
)

fake_home = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_home")
os.makedirs(fake_home, exist_ok=True)

env = {
    "HOME": fake_home,  # so Path.home()/"exo_passwd.txt" lands here, not your real home
    "PATH": "/usr/bin:/bin",
}

# note: this script also hardcodes /tmp/exo_pwned_marker.txt, /tmp/exo_passwd_dump.txt,
# /tmp/passwd_leaked.txt (not HOME-relative) - those land in the real shared /tmp
# regardless of env scrubbing, same as every other repo's marker/evidence files so far.
result = subprocess.run(["python3", SCRIPT], env=env, capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print("=== stderr ===")
    print(result.stderr)

print("=== files written ===")
for path in [
    "/tmp/exo_pwned_marker.txt",
    "/tmp/exo_passwd_dump.txt",
    "/tmp/passwd_leaked.txt",
    os.path.join(fake_home, "exo_passwd.txt"),
    "/tmp/exo_sysinfo.txt",
]:
    print(f"  [{'exists' if os.path.exists(path) else 'missing'}] {path}")
