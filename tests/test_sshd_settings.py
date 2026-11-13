"""The Remote login check may only say "keys only" when Keepwell read every
file sshd reads and accounted for sshd's command line. Any unreadable file
makes the result unsure, however early the global settings were decided,
because a Match block in it would override them. So does an Include it
doesn't follow, -f or a Match/Include given with -o, and a Match block
(Match All included) that turns passwords or root login back on.
Each sshd that can be reached (sshd.service, and the socket's sshd@.service)
is resolved on its own, so a hardened unit not in use can't mask one that is.

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
SSHD = "/usr/bin/sshd"
T = "sshd@keepwell-probe.service"
# What systemd 262 returns over D-Bus for Arch's units: exact argument lists.
STOCK = {"sshd.service": [(SSHD, [SSHD, "-D"])],
         "sshd@keepwell-probe.service": [(SSHD, [SSHD, "-i", "-o", "AuthorizedKeysFile ${CREDENTIALS_DIRECTORY}"
                                                 "/ssh.ephemeral-authorized_keys-all .ssh/authorized_keys"])]}

MAIN = b"Include /etc/ssh/sshd_config.d/*.conf\nKbdInteractiveAuthentication no\n"
KEYS = b"PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n"
D = "/etc/ssh/sshd_config.d/"


SOCKET = {"accept": True, "ports": ["22"], "triggers": [], "other": False}


UNITDIRS = {"/etc/systemd/system": ["sshd@.service.d", "multi-user.target.wants"],
            "/usr/lib/systemd/system": ["sshd.service", "sshd@.service"]}


def settings(files, units=None, service=True, socket=None, unitdirs=None, loaded=()):
    """files: {path: bytes, or None for unreadable}; units: ExecStart per
    unit as [(path, argv)], or None when systemd gave no answer; service:
    sshd.service is enabled or running; socket: sshd.socket's settings when
    it is enabled or running ("none" when systemd gave no answer);
    unitdirs: systemd's unit folders and their entries (a value of None is
    unreadable); loaded: the sshd@ units loaded now (None: no answer)."""
    unitdirs = UNITDIRS if unitdirs is None else unitdirs
    names = sorted(os.path.basename(p) for p in files if p.startswith(D))
    units = dict(STOCK, **(units or {}))
    g["_sshd_file"] = lambda path: files.get(path)
    g["_unit_exec_start"] = lambda unit: units.get(unit)
    g["_sshd_socket"] = lambda: None if socket == "none" else socket
    g["text"] = lambda argv, **kw: (0, "\n".join(unitdirs) + "\n") if argv[-1] == "unit-paths" else (1, "")
    g["_unit_list"] = lambda pattern: None if loaded is None else [T] + list(loaded)

    def listdir(d):
        if d == D.rstrip("/"):
            return names
        if d in unitdirs:
            if unitdirs[d] is None:
                raise PermissionError(13, "Permission denied")
            return unitdirs[d]
        return real_listdir(d)
    os.listdir = listdir
    try:
        return check["_sshd_settings"](service_used=service, socket_used=socket is not None)
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


def cmd(*args, unit="sshd.service", path=SSHD):
    return {unit: [(path, [path] + list(args))]}


for name, args, passwords, unsure in (
        ("-o PasswordAuthentication=yes", ["-D", "-o", "PasswordAuthentication=yes"], True, False),
        ("-oPasswordAuthentication=yes (joined)", ["-D", "-oPasswordAuthentication=yes"], True, False),
        # The reported case: one argument holding a space, which sshd -T
        # confirms enables passwords over a file's "no".
        ("-o \"PasswordAuthentication yes\"", ["-D", "-o", "PasswordAuthentication yes"], True, False),
        ("-o\"PasswordAuthentication yes\" (joined)", ["-D", "-oPasswordAuthentication yes"], True, False),
        ("-o \"KbdInteractiveAuthentication yes\"", ["-D", "-o", "KbdInteractiveAuthentication yes"], True, False),
        ("-o \"PermitRootLogin yes\" keeps passwords off", ["-D", "-o", "PermitRootLogin yes"], False, False),
        ("-f other file", ["-D", "-f", "/etc/other"], False, True),
        ("-Df other file (cluster)", ["-Df/etc/other"], False, True),
        ("-o \"Match all\"", ["-D", "-o", "Match all"], False, True),
        ("-o Include", ["-D", "-o", "Include /etc/x.conf"], False, True),
        ("$OPTS", ["-D", "$SSHD_OPTS"], False, True),
        ("${OPTS}", ["-D", "${SSHD_OPTS}"], False, True),
        ("-o with a variable in a reported key", ["-D", "-o", "PasswordAuthentication ${PW}"], False, True),
        ("-o with a variable as the key", ["-D", "-o", "${KEY} yes"], False, True),
        ("-p with a variable", ["-D", "-p", "$PORT"], False, True)):
    expect(name, settings(files, cmd(*args)), passwords, unsure)
expect("-o on the socket's unit", settings(files, cmd("-i", "-o", "PasswordAuthentication yes", unit=T),
                                           service=False, socket=SOCKET), True, False)
expect("-o Match on the socket's unit", settings(files, cmd("-i", "-o", "Match=all", unit=T),
                                                 service=False, socket=SOCKET), False, True)
expect("started through a wrapper", settings(files, cmd("-D", path="/usr/local/bin/start-sshd")), False, True)
expect("command line unreadable", settings(files, {"sshd.service": None}), False, True)
expect("socket's command line unreadable", settings(files, {T: None}, socket=SOCKET), False, True)

# Each sshd that can be reached is resolved on its own: the reported case is
# a hardened unit that isn't in use masking the one that is.
OPEN = {"/etc/ssh/sshd_config": b"PasswordAuthentication yes\n"}
HARD = ["-o", "PasswordAuthentication no", "-o", "KbdInteractiveAuthentication no"]
expect("hardened socket unit not in use, sshd.service open", settings(OPEN, cmd("-i", *HARD, unit=T)), True, False)
expect("hardened sshd.service not in use, socket open",
       settings(OPEN, cmd("-D", *HARD), service=False, socket=SOCKET), True, False)
expect("hardened sshd.service in use, socket open too",
       settings(OPEN, cmd("-D", *HARD), service=True, socket=SOCKET), True, False)
expect("both hardened", settings(OPEN, dict(cmd("-D", *HARD), **cmd("-i", *HARD, unit=T)),
                                 socket=SOCKET), False, False)
expect("nothing in use reads sshd.service", settings(OPEN, cmd("-i", *HARD, unit=T), service=False), True, False)
r = settings(files, dict(cmd("-D", "-o", "PermitRootLogin no"), **cmd("-i", "-o", "PermitRootLogin yes", unit=T)),
             socket=SOCKET)
if r["rootLogin"] != "yes":
    bad.append("the most open root login wins: %r" % r)

# sshd.socket: Accept=yes starts sshd@.service on the socket's ports;
# Accept=no starts sshd.service; anything else is unsure.
r = settings(files, service=False, socket=dict(SOCKET, ports=["2222"]))
if r["port"] != "2222" or r["unsure"]:
    bad.append("socket port: %r" % r)
expect("Accept=no starts sshd.service", settings(OPEN, cmd("-i", *HARD, unit=T), service=False,
       socket=dict(SOCKET, accept=False, triggers=["sshd.service"])), True, False)
expect("socket starts another service", settings(files, service=False,
       socket=dict(SOCKET, accept=False, triggers=["other.service"])), False, True)
expect("socket listener Keepwell can't read", settings(files, socket=dict(SOCKET, other=True)), False, True)
expect("socket unreadable", settings(files, socket="none"), False, True)

# The reported case: an override for single connections while the template
# stays hardened. A connection loaded now is resolved with its own command
# line; one not started yet can't be, so any override for one is unsure.
I = "sshd@3-192.0.2.1:22-198.51.100.7:50122.service"
both = dict(cmd("-i", *HARD, unit=T), **cmd("-i", "-o", "PasswordAuthentication yes", unit=I))
expect("loaded connection with passwords on", settings(OPEN, both, service=False, socket=SOCKET,
                                                       loaded=[I]), True, False)
expect("loaded connection, hardened", settings(OPEN, dict(cmd("-i", *HARD, unit=T), **cmd("-i", *HARD, unit=I)),
                                               service=False, socket=SOCKET, loaded=[I]), False, False)
for entry in (I, I + ".d", "sshd@3-.service.d", "sshd@keepwell-.service.d"):
    expect("override %s" % entry, settings(files, service=False, socket=SOCKET,
           unitdirs=dict(UNITDIRS, **{"/etc/systemd/system.control": [entry]})), False, True)
expect("unit folder unreadable", settings(files, service=False, socket=SOCKET,
       unitdirs=dict(UNITDIRS, **{"/run/systemd/system": None})), False, True)
expect("unit folders unknown", settings(files, service=False, socket=SOCKET, unitdirs={}), False, True)
expect("connections not listed", settings(files, service=False, socket=SOCKET, loaded=None), False, True)
expect("more than 20 connections", settings(files, service=False, socket=SOCKET,
       loaded=["sshd@%d-x.service" % n for n in range(21)]), False, True)
expect("overrides don't matter without Accept=yes", settings(files, unitdirs=dict(UNITDIRS, **{
       "/etc/systemd/system": [I + ".d"]})), False, False)

# Ports add up, as sshd -T shows: every Port, or only -p's; a ListenAddress
# with a port uses only that port; Port under Match All still applies.
for name, conf, args, want in (
        ("-p", b"", ["-D", "-p", "2222"], "2222"),
        ("two Ports", b"Port 22\nPort 2222\n", ["-D"], "22, 2222"),
        ("-p over Port", b"Port 2222\n", ["-D", "-p", "3333"], "3333"),
        ("-o Port adds", b"Port 2222\n", ["-D", "-o", "Port=5555"], "2222, 5555"),
        ("ListenAddress with a port", b"Port 8888\nListenAddress 0.0.0.0:7777\n", ["-D"], "7777"),
        ("ListenAddress with and without", b"Port 2222\nListenAddress 0.0.0.0:4444\nListenAddress [::]\n",
         ["-D"], "2222, 4444"),
        ("bare IPv6 ListenAddress", b"ListenAddress ::\nPort 2222\n", ["-D"], "2222"),
        ("Port under Match All", b"Match All\nPort 1234\n", ["-D"], "1234")):
    r = settings({"/etc/ssh/sshd_config": conf + KEYS}, cmd(*args))
    if r["port"] != want:
        bad.append("%s: %r" % (name, r))

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: keys only is claimed only when every file and option sshd reads was accounted for")
