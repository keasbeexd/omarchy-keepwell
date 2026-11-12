"""A deep scan's summary must have a line for every part it was asked to
run, built only from results that part's own run made. A virus scan whose
log couldn't be written, a part that couldn't start, or the Downloads log
standing in for the home folder scan must never read as clean or vanish.

Run: python3 tests/test_deep_summary.py
"""

import contextlib
import io
import json
import os
import runpy
import shutil
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
home = tempfile.mkdtemp(prefix="keepwell-test-")
os.environ["HOME"] = home
sys.path.insert(0, str(root / "bin"))
run = runpy.run_path(str(root / "bin" / "keepwell-run"), run_name="keepwell_run")
g = run["run"].__globals__
state = g["keepwell_state"]
summary = run["_deep_summary"]

CLEAN = """
----------- SCAN SUMMARY -----------
Scanned files: 5
Infected files: 0
Keepwell: clamscan exit status 0
"""

bad = []


def check(name, text, must=(), never=()):
    for m in must:
        if m.lower() not in text.lower():
            bad.append("%s: %r lacks %r" % (name, text, m))
    for m in never:
        if m.lower() in text.lower():
            bad.append("%s: %r has %r" % (name, text, m))


def write_log(kind):
    path = state.new_log(kind)
    with open(path, "w") as f:
        f.write(CLEAN)


# Earlier clean results of every kind.
write_log("downloads")
write_log("home")
state.write("gitleaks.json", json.dumps({"at": int(time.time()), "finished": True, "scanned": 1,
                                         "failed": 0, "findings": []}).encode())
state.write("osv.json", json.dumps({"at": int(time.time()), "finished": True, "scanned": 1,
                                    "failed": 0, "findings": [], "packages": 0}).encode())
time.sleep(1.1)
since = int(time.time())

# The reported case: a virus-only deep scan whose log was never created.
check("virus-only, no log", summary(["scan-downloads"], {"scan-downloads": ("started", since)}, []),
      must=["virus scan of Downloads failed"], never=["nothing found", "Nothing to scan"])

# All four parts started, none wrote a result of its own.
parts = ["scan-downloads", "scan-home", "leaks", "osv"]
text = summary(parts, {p: ("started", since) for p in parts}, [])
check("nothing written", text,
      must=["Downloads failed", "home folder failed", "secrets scan stopped", "dependencies scan stopped"],
      never=["nothing found", "no secrets", "no vulnerable", "Nothing to scan"])

# Downloads wrote a clean log; the home scan didn't. The Downloads log must
# not answer for the home folder.
time.sleep(1.1)
write_log("downloads")
text = summary(["scan-downloads", "scan-home"],
               {"scan-downloads": ("started", since), "scan-home": ("started", since)}, [])
check("downloads only", text, must=["virus scan of Downloads: nothing found", "home folder failed"],
      never=["home folder: nothing found"])

# Parts that never ran are named.
text = summary(parts, {"scan-downloads": ("busy", since), "scan-home": ("failed", since),
                       "leaks": ("nofolder", since), "osv": ("running", since)}, [])
check("not run", text, must=["another one was still running", "couldn't be started",
                             "folder no longer exists", "still running after 12 hours"],
      never=["nothing found", "no secrets", "no vulnerable"])

# A missing tool is said once, by the skip line.
text = summary(["osv"], {"osv": ("missing", since)}, ["dependencies scan needs osv-scanner"])
check("missing tool", text, must=["needs osv-scanner"], never=["stopped"])

# A part with no entry in runs at all counts as not started.
check("no entry", summary(["leaks"], {}, []), must=["couldn't be started"], never=["no secrets"])

# Whole run, with a scan that starts but never writes its log, and a state
# folder that can't save the result: the notification still goes out.
said = []
g["_notify"] = lambda title, body: said.append(body)
g["_wait"] = lambda unit, limit=0: True
g["start_scan"] = lambda target, quiet=False: {"started": True}
g["on_battery"] = lambda: False
sched = g["keepwell_schedule"]
real_settings, real_save = sched.settings, sched.save_run
sched.settings = lambda: {"deep": {"parts": ["scan-home"], "battery": False}}


def cant_save(*a, **k):
    raise OSError(28, "No space left on device")


sched.save_run = cant_save
with contextlib.redirect_stdout(io.StringIO()):
    run["run"]("deep", False)
sched.settings, sched.save_run = real_settings, real_save
if not said:
    bad.append("no notification when the run couldn't be saved")
else:
    check("whole run", said[-1], must=["home folder failed", "couldn't save this result"],
          never=["nothing found", "Nothing to scan"])

shutil.rmtree(home, ignore_errors=True)
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: every deep scan part is reported from its own run")
