"""An accepted finding stays listed but must leave every count that can
raise a check or send a notification, and must come back when it changes.
Covers the keys (bin/keepwell_accept.py), the runner's accept command, and
the gitleaks/osv-scanner notifications and deep-scan summary.

Run: python3 tests/test_accept.py
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
g = run["notify"].__globals__
state, acc = g["keepwell_state"], g["keepwell_accept"]
said = []
g["_notify"] = lambda title, body: said.append((title, body))
g["_refresh"] = lambda: None
bad = []


def main(*args):
    """The runner's command line, run in this process (HOME is the test's)."""
    out = io.StringIO()
    sys.argv = ["keepwell-run"] + list(args)
    with contextlib.redirect_stdout(out):
        rc = run["main"]()
    return rc, out.getvalue()


# Keys: stable, and different when anything that describes the finding does.
k = acc.audit_key("openssl", "High", "3.0.1", ["CVE-2026-1", "CVE-2026-2"])
if k != acc.audit_key("openssl", "High", "3.0.1", ["CVE-2026-2", "CVE-2026-1"]):
    bad.append("audit key depends on CVE order")
for name, other in (("new CVE", acc.audit_key("openssl", "High", "3.0.1", ["CVE-2026-1", "CVE-2026-2", "CVE-2026-3"])),
                    ("new fix", acc.audit_key("openssl", "High", "3.0.2", ["CVE-2026-1", "CVE-2026-2"])),
                    ("severity", acc.audit_key("openssl", "Critical", "3.0.1", ["CVE-2026-1", "CVE-2026-2"]))):
    if other == k:
        bad.append("audit key unchanged by %s" % name)
DEP = {"repo": "app", "file": "package-lock.json", "package": "lodash", "version": "4.17.20",
       "vulns": [{"id": "GHSA-1"}], "fixable": True}
d = acc.dep_key("~", DEP)
if d == acc.dep_key("~", dict(DEP, vulns=[{"id": "GHSA-1"}, {"id": "GHSA-2"}])) \
        or d == acc.dep_key("~", dict(DEP, version="4.17.21")):
    bad.append("dep key unchanged by a new vulnerability or version")
LEAK = {"repo": "app", "file": "config.py", "line": 3, "rule": "generic-api-key", "commit": "abcd1234"}
if acc.leak_key("~", LEAK) == acc.leak_key("~", dict(LEAK, commit="ffff0000")):
    bad.append("leak key unchanged by another commit")

# The store: only known checks and well-formed keys; on and off; a limit.
if acc.mark("remote", k, True) or acc.mark("audit", "not-a-key", True) or acc.mark("audit", k.upper(), True):
    bad.append("accepted an unknown check or a malformed key")
acc.mark("audit", k, True)
if k not in acc.accepted("audit"):
    bad.append("accept didn't stick")
acc.mark("audit", k, False)
if k in acc.accepted("audit"):
    bad.append("un-accept didn't stick")
for i in range(acc.LIMIT + 5):
    acc.mark("failed", "%016x" % i, True)
if len(acc.accepted("failed")) != acc.LIMIT or "%016x" % (acc.LIMIT + 4) not in acc.accepted("failed"):
    bad.append("limit keeps the wrong keys")
state.write(acc.FILE, b'{"accepted": {"audit": ["zz", 5, "%s"], "deps": "x"}}' % k.encode())
if acc.load()["audit"] != [k] or acc.load()["deps"] != []:
    bad.append("malformed store not filtered: %r" % acc.load())
state.write(acc.FILE, b"not json")
if any(acc.load().values()):
    bad.append("unreadable store taken as accepted")

# The runner's command.
rc, out = main("accept", "deps", "+" + d)
if rc != 0 or json.loads(out) != {"saved": True} or d not in acc.accepted("deps"):
    bad.append("accept command: %r %r" % (rc, out))
rc, out = main("accept", "deps", "+../../etc")
if rc == 0 or json.loads(out) != {"saved": False}:
    bad.append("accept command took a bad key: %r %r" % (rc, out))
# A batch with one bad change writes nothing.
rc, out = main("accept", "deps", "-" + d, "+zz")
if rc == 0 or d not in acc.accepted("deps"):
    bad.append("a batch with a bad change was partly applied: %r %r" % (rc, out))
other_key = acc.dep_key("~", dict(DEP, package="x"))
rc, out = main("accept", "deps", "+" + other_key, "-" + d)
if rc != 0 or other_key not in acc.accepted("deps") or d in acc.accepted("deps"):
    bad.append("batch accept and un-accept: %r" % acc.accepted("deps"))
main("accept", "deps", "+" + d, "-" + other_key)

# Notifications: the accepted finding is left out and counted as accepted.
since = int(time.time())
other = dict(DEP, package="minimist", vulns=[{"id": "GHSA-9"}], fixable=False)
state.write("osv.json", json.dumps({"at": since, "finished": True, "folder": "~", "scanned": 1, "failed": 0,
                                    "packages": 2, "findings": [DEP, other]}).encode())
run["notify"]("osv", False, since)
if "1 package with known vulnerabilities (0 fixable)" not in said[-1][1] or "(1 accepted)" not in said[-1][1]:
    bad.append("osv notification: %r" % (said[-1],))
acc.mark("deps", acc.dep_key("~", other), True)
run["notify"]("osv", False, since)
if not said[-1][1].startswith("No new vulnerabilities (2 accepted)"):
    bad.append("osv notification, all accepted: %r" % (said[-1],))

state.write("gitleaks.json", json.dumps({"at": since, "finished": True, "folder": "~", "scanned": 1, "failed": 0,
                                         "repos": 1, "findings": [LEAK]}).encode())
run["notify"]("gitleaks", False, since)
if "1 possible secret" not in said[-1][1]:
    bad.append("leaks notification before accepting: %r" % (said[-1],))
acc.mark("leaks", acc.leak_key("~", LEAK), True)
run["notify"]("gitleaks", False, since)
if not said[-1][1].startswith("No new secrets found (1 accepted)"):
    bad.append("leaks notification after accepting: %r" % (said[-1],))
# The same secret in a different commit is new.
state.write("gitleaks.json", json.dumps({"at": since, "finished": True, "folder": "~", "scanned": 1, "failed": 0,
                                         "repos": 1, "findings": [LEAK, dict(LEAK, commit="ffff0000")]}).encode())
run["notify"]("gitleaks", False, since)
if "1 possible secret" not in said[-1][1] or "(1 accepted)" not in said[-1][1]:
    bad.append("changed leak not shown again: %r" % (said[-1],))

# The deep-scan summary.
text = run["_deep_summary"](["leaks", "osv"], {"leaks": ("started", since), "osv": ("started", since)}, [])
if "1 possible secret" not in text or "no new vulnerable dependencies (2 accepted)" not in text:
    bad.append("deep summary: %r" % text)

shutil.rmtree(home, ignore_errors=True)
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: accepted findings are kept out of every count and come back when they change")
