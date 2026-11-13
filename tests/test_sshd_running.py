"""An sshd listener may only be ruled out when every process was read. A
process listed but not readable (hidepid=1, or any other refusal) or a
/proc that doesn't list PID 1 (hidepid=2) makes running programs unknown;
only a process that ended while being read is skipped. Uses a fake /proc.

Run: python3 tests/test_sshd_running.py
"""

import os
import runpy
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "bin"))
check = runpy.run_path(str(root / "bin" / "keepwell-check"), run_name="keepwell_check")
running = check["_sshd_running"]
bad = []


def proc(procs):
    """procs: {pid: (comm, cgroup) or "locked" or "gone" or ("sshd", "locked")}"""
    top = tempfile.mkdtemp(prefix="keepwell-proc-")
    for pid, what in procs.items():
        d = os.path.join(top, pid)
        os.makedirs(d)
        if what == "gone":
            continue
        comm, cg = ("x", "") if what == "locked" else what
        with open(os.path.join(d, "comm"), "w") as f:
            f.write(comm + "\n")
        with open(os.path.join(d, "cgroup"), "w") as f:
            f.write("0::%s\n" % cg if cg != "locked" else "")
        if cg == "locked":
            os.chmod(os.path.join(d, "cgroup"), 0)
        if what == "locked":
            os.chmod(d, 0)
    return top


def run(name, procs, want):
    top = proc(procs)
    try:
        unsure = []
        r = running(unsure, proc=top)
        got = (sorted(r["units"]), r["outside"], r["unknown"])
        if got != want or bool(unsure) is not (r["unknown"] or r["outside"] > 0):
            bad.append("%s: %r %r" % (name, got, unsure))
    finally:
        for dirpath, dirs, _ in os.walk(top):
            for d in dirs:
                os.chmod(os.path.join(dirpath, d), 0o700)
        shutil.rmtree(top, ignore_errors=True)


INIT = ("systemd", "/init.scope")
run("nothing running", {"1": INIT}, ([], 0, False))
run("sshd in a service", {"1": INIT, "50": ("sshd", "/system.slice/my-sshd.service")}, (["my-sshd.service"], 0, False))
run("sshd in a scope", {"1": INIT, "50": ("sshd", "/user.slice/user-1000.slice/session-2.scope")}, ([], 1, False))
run("sshd in a user service",
    {"1": INIT, "50": ("sshd", "/user.slice/user-1000.slice/user@1000.service/app.slice/x.service")}, ([], 1, False))
run("sshd-session isn't the listener", {"1": INIT, "50": ("sshd-session", "/system.slice/x.service")}, ([], 0, False))
run("process ended while being read", {"1": INIT, "50": "gone"}, ([], 0, False))
run("PID 1 not listed (hidepid=2)", {"50": ("sshd", "/system.slice/x.service")}, ([], 0, True))
if os.geteuid() != 0:
    # The reported case: hidepid=1 lists other users' processes but
    # refuses to read them.
    run("process listed but unreadable (hidepid=1)", {"1": INIT, "50": "locked"}, ([], 0, True))
    run("sshd whose cgroup is unreadable", {"1": INIT, "50": ("sshd", "locked")}, ([], 0, True))
else:
    print("note: running as root, so the unreadable cases were skipped")

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: an sshd is ruled out only when every process was read")
