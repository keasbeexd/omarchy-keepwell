"""The notification at the end of a background scan must describe that run,
never an earlier one. With a clean log or summary from an earlier scan in
place, a run that fails before it writes its own result (the file list
can't be written on a full disk, the log can't be created) must not be
announced as "finished ... nothing found".

Run: python3 tests/test_notify_binding.py
"""

import json
import os
import runpy
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
home = tempfile.mkdtemp(prefix="keepwell-test-")
os.environ["HOME"] = home
sys.path.insert(0, str(root / "bin"))
run = runpy.run_path(str(root / "bin" / "keepwell-run"), run_name="keepwell_run")
g = run["notify"].__globals__
state = g["keepwell_state"]
said = []
g["_notify"] = lambda title, body: said.append((title, body))
g["_refresh"] = lambda: None

CLEAN = """
----------- SCAN SUMMARY -----------
Scanned files: 5
Infected files: 0
Time: 3.000 sec (0 m 3 s)
Keepwell: clamscan exit status 0
"""

bad = []


def last():
    return said[-1] if said else ("", "")


# An earlier, clean scan.
earlier = state.new_log("downloads")
with open(earlier, "w") as f:
    f.write(CLEAN)
time.sleep(1.1)

# 1. The new run fails before it creates its log: nothing newer than its start.
since = int(time.time())
run["notify"]("clamscan", False, since)
if last()[0] != "Virus scan failed" or "nothing found" in last()[1]:
    bad.append("no log from this run: %r" % (last(),))

# 2. The new run creates its log, then writing the file list fails.
os.makedirs(os.path.join(home, "Downloads"), exist_ok=True)
open(os.path.join(home, "Downloads", "a.txt"), "w").close()


def full(*_):
    raise OSError(28, "No space left on device")


g["_list_files"] = full
since = int(time.time())
try:
    run["clam_scan"]("downloads")
    bad.append("clam_scan did not fail when the file list couldn't be written")
except OSError:
    pass
run["notify"]("clamscan", False, since)
if last()[0] != "Virus scan stopped" or "nothing found" in last()[1]:
    bad.append("file list write failed: %r" % (last(),))

# 3. The earlier clean log is still announced correctly by its own run.
run["notify"]("clamscan", False, int(os.path.basename(earlier)[:10]))
# (the newest log is now the failed run's, so this must not say finished either)
if last()[0] == "Virus scan finished":
    bad.append("older run's notify picked up a newer log as finished")

# 4. Secrets and dependency scans: an earlier finished summary is not this run's.
for kind, key, word in (("gitleaks", "gitleaks.json", "Secrets"), ("osv", "osv.json", "Dependency")):
    doc = {"at": int(time.time()) - 60, "finished": True, "scanned": 1, "failed": 0, "findings": [], "packages": 0}
    state.write(key, json.dumps(doc).encode())
    run["notify"](kind, False, int(time.time()))
    if last()[0] != "%s scan stopped" % word:
        bad.append("%s: earlier summary announced as this run's: %r" % (kind, last()))
    run["notify"](kind, False, doc["at"])
    if last()[0] != "%s scan finished" % word:
        bad.append("%s: its own run's summary not announced: %r" % (kind, last()))

# 5. The command line requires --since.
import contextlib, io, shutil  # noqa: E402,E401
sys.argv = ["keepwell-run", "notify", "clamscan"]
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    try:
        rc = run["main"]()
    except SystemExit as e:
        rc = e.code
shutil.rmtree(home, ignore_errors=True)
if rc in (0, None):
    bad.append("notify without --since was accepted")

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: notifications are bound to their own run")
