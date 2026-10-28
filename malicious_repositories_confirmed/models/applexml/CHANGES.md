# Changes made for local testing

None. No network callback in this one - it reads `/etc/passwd` (world-readable, not
a privileged leak) and writes copies to local files. Nothing needed fixing to test it
safely.
