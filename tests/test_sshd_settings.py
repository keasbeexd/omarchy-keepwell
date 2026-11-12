"""The Remote login check may only say "keys only" when Keepwell read every
file sshd reads up to the point the settings are decided. An unreadable
drop-in before that point, an Include it doesn't follow, or a Match block
that turns passwords back on must make the result unsure.

Run: python3 tests/test_sshd_settings.py
"""

import os
import runpy
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "bin"))
check = runpy.run_path(str(root / "bin" / "keepwell-check"), run_name="keepwell_check")
g = check["_sshd_settings"].__globals__
real_listdir = os.listdir

MAIN = b"Include /etc/ssh/sshd_config.d/*.conf\nKbdInteractiveAuthentication no\n"
KEYS = b"PasswordAuthentication no\nKbdInteractiveAuthentication no\n"


def settings(files, folder=None):
    """files: {path: bytes or None (unreadable)}."""
    names = sorted(os.path.basename(p) for p in files if p.startswith("/etc/ssh/sshd_config.d/"))
    g["_sshd_file"] = lambda path: files.get(path)
    os.listdir = lambda d: (folder if folder is not None else names) if d == "/etc/ssh/sshd_config.d" else real_listdir(d)
    try:
        return check["_sshd_settings"]()
    finally:
        os.listdir = real_listdir


bad = []
d = "/etc/ssh/sshd_config.d/"

r = settings({"/etc/ssh/sshd_config": MAIN, d + "10-keepwell-keys-only.conf": KEYS})
if r["passwords"] or r["unsure"]:
    bad.append("keys only, all readable: %r" % r)

# An unreadable file after every setting is decided can't change anything.
r = settings({"/etc/ssh/sshd_config": MAIN + b"PermitRootLogin no\n",
              d + "10-keepwell-keys-only.conf": KEYS + b"PermitRootLogin no\n", d + "20-userdb.conf": None})
if r["passwords"] or r["unsure"]:
    bad.append("unreadable file after the settings: %r" % r)

# An unreadable file before the decision could turn passwords on.
r = settings({"/etc/ssh/sshd_config": MAIN, d + "05-vendor.conf": None, d + "10-keepwell-keys-only.conf": KEYS})
if not r["unsure"]:
    bad.append("unreadable file before the settings: %r" % r)

# A Match block allowing passwords for some connections.
r = settings({"/etc/ssh/sshd_config": MAIN + b"Match Address 10.0.0.0/8\n  PasswordAuthentication yes\n",
              d + "10-keepwell-keys-only.conf": KEYS})
if r["passwords"] or not any("Match" in u for u in r["unsure"]):
    bad.append("Match block allowing passwords: %r" % r)

# An Include outside /etc/ssh, or with a glob Keepwell doesn't expand.
r = settings({"/etc/ssh/sshd_config": b"Include /opt/ssh/*.conf\n" + KEYS})
if not r["unsure"]:
    bad.append("Include outside /etc/ssh: %r" % r)
r = settings({"/etc/ssh/sshd_config": b"Include /etc/ssh/sshd_config.d/?.conf\n" + KEYS})
if not r["unsure"]:
    bad.append("Include with ?: %r" % r)

# Passwords on in the first file sshd reads.
r = settings({"/etc/ssh/sshd_config": MAIN, d + "01-on.conf": b"PasswordAuthentication yes\n",
              d + "10-keepwell-keys-only.conf": KEYS})
if not r["passwords"]:
    bad.append("first value wins: %r" % r)

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: keys only is claimed only when every file that decides it was read")
