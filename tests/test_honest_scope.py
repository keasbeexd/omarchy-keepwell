"""Four places where Keepwell must not claim more than it does:

- Turn off SSH stops sshd.socket too when it is installed, never promises
  that nobody can log in, and says when an sshd started another way keeps
  running.
- Software outside updates never says omarchy update covers everything
  while packages haven't been checked against the AUR.
- Turning the schedule off leaves a keepwell-deep timer that systemd
  loaded from someone else's file alone.
- An unclaimed folder with anything inside that can't be read is never
  called untouched.

Run: python3 tests/test_honest_scope.py
"""

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
home = tempfile.mkdtemp(prefix="keepwell-test-")
os.environ["HOME"] = home
sys.path.insert(0, str(root / "bin"))
run = runpy.run_path(str(root / "bin" / "keepwell-run"), run_name="keepwell_run")
g = run["plan"].__globals__
bad = []

# Turn off SSH.
real_capture = g["capture"]
for state, socket in (("loaded", True), ("not-found", False), ("", True)):
    g["capture"] = lambda argv, **kw: state if "LoadState" in argv else real_capture(argv, **kw)
    argv = run["ACTIONS"]["ssh-off"]["steps"](set())[0]["argv"]
    argv = argv[2:] if argv[:2] == ["/usr/bin/sudo", "--"] else argv   # root steps run through sudo
    if ("sshd.socket" in argv) is not socket or "sshd.service" not in argv or argv[:4] != ["/usr/bin/systemctl", "disable", "--now", "--"]:
        bad.append("ssh-off with sshd.socket %r: %r" % (state, argv))
g["capture"] = real_capture
summary = run["ACTIONS"]["ssh-off"]["summary"]
if "Nobody can log in" in summary or "left alone" not in summary:
    bad.append("ssh-off summary claims too much: %r" % summary)

# The schedule: a timer from another file is left alone.
calls = []
g["_user_systemctl"] = lambda *a: calls.append(a) or 0
sched = g["keepwell_schedule"]
real_capture = g["capture"]
g["capture"] = lambda argv, **kw: "/etc/systemd/user/keepwell-deep.timer\n" if "FragmentPath" in argv else ""
r = run["schedule_off"]("deep")
if r.get("saved") is not False or calls:
    bad.append("schedule off touched another file's timer: %r %r" % (r, calls))
r = run["schedule_set"]("deep", "mon", "03:00", "leaks", "on")
if r.get("saved") is not False or r.get("reason") != "exists" or calls:
    bad.append("schedule on replaced another file's timer: %r %r" % (r, calls))
st = sched.status(lambda argv: "enabled\n" if "is-enabled" in argv
                  else "/etc/systemd/user/keepwell-deep.timer\n" if "FragmentPath" in argv else "")
if st["deep"]["enabled"]:
    bad.append("another file's timer counted as the schedule being on")
# Keepwell's own: turned off as before.
g["capture"] = lambda argv, **kw: ""
r = run["schedule_off"]("deep")
if r.get("saved") is not True:
    bad.append("schedule off with no timer: %r" % r)
g["capture"] = real_capture

# Unclaimed folders.
unclaimed = g["keepwell_unclaimed"]
top = os.path.join(home, ".config", "oldapp")
os.makedirs(os.path.join(top, "cache", "inner"))
old = time.time() - 400 * 86400
for d in (os.path.join(top, "cache", "inner"), os.path.join(top, "cache"), top):
    os.utime(d, (old, old))
newest, size, complete = unclaimed._look(top, [8000], time.monotonic() + 4)
if not complete:
    bad.append("a readable old folder counted as incomplete")
if os.geteuid() != 0:
    os.chmod(os.path.join(top, "cache"), 0)
    os.utime(top, (old, old))
    try:
        newest, size, complete = unclaimed._look(top, [8000], time.monotonic() + 4)
        if complete:
            bad.append("a folder with an unreadable subfolder counted as complete")
    finally:
        os.chmod(os.path.join(top, "cache"), 0o700)
else:
    print("note: running as root, so the unreadable folder wasn't tested")

# What the window shows (Present.js under node).
node = shutil.which("node")
if node:
    def body(name):
        text = (root / "model" / name).read_text()
        return "\n".join(l for l in text.splitlines() if not l.startswith((".pragma", ".import")))
    status = body("Status.js")
    names = re.findall(r"^function ([A-Za-z0-9_]+)", status, re.M)
    NOW = 2000000000
    script = status + "\nvar Status = {%s};\n" % ",".join("%s: %s" % (n, n) for n in names) + body("Present.js") + """
var out = [];
function o(p) { var r = outside(p, {}, %d); out.push([r.kind, r.status, (r.actions || []).map(function(a) { return a.run || a.act })]) }
o({ foreign: 3, unchecked: 3, aurAt: null, inAur: [], notInAur: [], hand: [] });
o({ foreign: 3, unchecked: 0, aurAt: %d, inAur: ["a", "b", "c"], notInAur: [], hand: [] });
o({ foreign: 4, unchecked: 1, aurAt: %d, inAur: ["a", "b", "c"], notInAur: [], hand: [] });
var base = { installed: true, enabled: "disabled", active: "inactive", socket: false, passwords: true, rootLogin: "no",
             port: "22", unsure: [], firewallAllows: false, authorizedKeys: 0, keepwellKeysOnly: false };
var r1 = remote(Object.assign({}, base, { active: "active", elsewhere: ["my-sshd.service"] }));
var r2 = remote(Object.assign({}, base, { active: "active" }));
out.push([r1.note.indexOf("keeps running") !== -1, (r2.note || "").indexOf("keeps running") !== -1]);
console.log(JSON.stringify(out));
""" % (NOW, NOW - 600, NOW - 600)
    proc = subprocess.run([node, "-"], input=script.encode(), capture_output=True, timeout=30)
    got = json.loads(proc.stdout) if proc.returncode == 0 else None
    if not got:
        bad.append("Present.js didn't run: " + proc.stderr.decode()[-500:])
    else:
        before, checked, one_new, notes = got
        if before[0] == "good" or "covers everything" in before[1] or "network" not in before[2]:
            bad.append("before the first AUR lookup: %r" % before)
        if checked[0] != "good" or "covers everything" not in checked[1]:
            bad.append("all checked: %r" % checked)
        if one_new[0] == "good" or "covers everything" in one_new[1]:
            bad.append("a package new since the last lookup: %r" % one_new)
        if notes != [True, False]:
            bad.append("Turn off SSH note about another sshd: %r" % notes)
else:
    print("note: node isn't installed, so what the checks show wasn't run")

shutil.rmtree(home, ignore_errors=True)
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: Turn off SSH, update coverage, the schedule and unclaimed folders claim only what they do")
