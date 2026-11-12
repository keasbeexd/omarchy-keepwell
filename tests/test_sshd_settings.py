"""The Remote login check may only say "keys only" when Keepwell read every
file sshd reads and accounted for sshd's command line. Any unreadable file
makes the result unsure, however early the global settings were decided,
because a Match block in it would override them. So does an Include it
doesn't follow, -f or a Match/Include given with -o, and a Match block
(Match All included) that turns passwords or root login back on.

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
STOCK = {"sshd.service": "{ path=/usr/bin/sshd ; argv[]=/usr/bin/sshd -D ; ignore_errors=no ; }",
         "sshd@keepwell-probe.service": "{ path=/usr/bin/sshd ; argv[]=/usr/bin/sshd -i -o AuthorizedKeysFile "
                                        "${CREDENTIALS_DIRECTORY}/ssh.ephemeral-authorized_keys-all .ssh/authorized_keys ; }"}

MAIN = b"Include /etc/ssh/sshd_config.d/*.conf\nKbdInteractiveAuthentication no\n"
KEYS = b"PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n"
D = "/etc/ssh/sshd_config.d/"


def settings(files, units=None):
    """files: {path: bytes, or None for unreadable}; units: ExecStart per unit."""
    names = sorted(os.path.basename(p) for p in files if p.startswith(D))
    units = dict(STOCK, **(units or {}))
    g["_sshd_file"] = lambda path: files.get(path)
    g["text"] = lambda argv, **kw: (0, units[argv[-1]]) if units.get(argv[-1]) is not None else (1, "")
    os.listdir = lambda d: names if d == D.rstrip("/") else real_listdir(d)
    try:
        return check["_sshd_settings"]()
    finally:
        os.listdir = real_listdir


bad = []


def expect(name, r, passwords, unsure):
    if r["passwords"] is not passwords or bool(r["unsure"]) is not unsure:
        bad.append("%s: %r" % (name, r))


expect("keys only, all readable",
       settings({"/etc/ssh/sshd_config": MAIN, D + "10-keepwell-keys-only.conf": KEYS}), False, False)

# The reported case: globals already disable passwords and root login, and a
# later file can't be read. It may hold a Match block that overrides them.
expect("unreadable file after the globals",
       settings({"/etc/ssh/sshd_config": MAIN, D + "10-keepwell-keys-only.conf": KEYS, D + "20-x.conf": None}),
       False, True)
expect("unreadable file before the globals",
       settings({"/etc/ssh/sshd_config": MAIN, D + "05-vendor.conf": None, D + "10-keepwell-keys-only.conf": KEYS}),
       False, True)
expect("unreadable main config", settings({"/etc/ssh/sshd_config": None}), True, True)

# Match blocks, including Match All, and AuthenticationMethods inside one.
for name, block in (("Match Address", b"Match Address 10.0.0.0/8\n  PasswordAuthentication yes\n"),
                    ("Match All", b"Match All\nPasswordAuthentication yes\n"),
                    ("Match User root", b"Match User root\n  PermitRootLogin yes\n"),
                    ("Match Include", b"Match User x\n  Include /etc/ssh/extra.conf\n"),
                    ("Match keyword=value", b"Match Group admins\n  PasswordAuthentication=yes\n")):
    expect(name, settings({"/etc/ssh/sshd_config": MAIN + block, D + "10-keepwell-keys-only.conf": KEYS}),
           False, True)
expect("Match in a later readable file",
       settings({"/etc/ssh/sshd_config": MAIN, D + "10-keepwell-keys-only.conf": KEYS,
                 D + "50-x.conf": b"Match User bob\n\tPasswordAuthentication \"yes\"\n"}), False, True)

# sshd's syntax: Keyword=value and quoted values count like Keyword value.
expect("Keyword=value first", settings({"/etc/ssh/sshd_config": MAIN, D + "01-on.conf": b"PasswordAuthentication=yes\n",
                                        D + "10-keepwell-keys-only.conf": KEYS}), True, False)
expect("quoted value first", settings({"/etc/ssh/sshd_config": MAIN, D + "01-on.conf": b'PasswordAuthentication "yes"\n',
                                       D + "10-keepwell-keys-only.conf": KEYS}), True, False)
expect("first value wins", settings({"/etc/ssh/sshd_config": MAIN, D + "01-on.conf": b"PasswordAuthentication yes\n",
                                     D + "10-keepwell-keys-only.conf": KEYS}), True, False)

# Includes Keepwell doesn't follow.
expect("Include outside /etc/ssh", settings({"/etc/ssh/sshd_config": b"Include /opt/ssh/*.conf\n" + KEYS}), False, True)
expect("Include with ?", settings({"/etc/ssh/sshd_config": b"Include /etc/ssh/sshd_config.d/?.conf\n" + KEYS}), False, True)

# sshd's command line.
files = {"/etc/ssh/sshd_config": MAIN, D + "10-keepwell-keys-only.conf": KEYS}
expect("stock units", settings(files), False, False)
expect("-o PasswordAuthentication=yes", settings(files, {"sshd.service":
       "{ argv[]=/usr/bin/sshd -D -o PasswordAuthentication=yes ; }"}), True, False)
expect("-oPasswordAuthentication yes (joined)", settings(files, {"sshd.service":
       "{ argv[]=/usr/bin/sshd -D -oPasswordAuthentication=yes ; }"}), True, False)
expect("-f other file", settings(files, {"sshd.service": "{ argv[]=/usr/bin/sshd -D -f /etc/other ; }"}), False, True)
expect("-Df other file (cluster)", settings(files, {"sshd.service": "{ argv[]=/usr/bin/sshd -Df/etc/other ; }"}),
       False, True)
expect("-o Match", settings(files, {"sshd@keepwell-probe.service": "{ argv[]=/usr/bin/sshd -i -o Match=all ; }"}),
       False, True)
expect("command line unreadable", settings(files, {"sshd.service": None}), False, True)
r = settings(files, {"sshd.service": "{ argv[]=/usr/bin/sshd -D -p 2222 ; }"})
if r["port"] != "2222":
    bad.append("-p port: %r" % r)

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: keys only is claimed only when every file and option sshd reads was accounted for")
