"""What the window shows for accepted findings (model/Present.js): greyed
rows with a ticked box, left out of the check's state and status, so a
check whose every finding is accepted can't raise the shield or a
notification. Runs Present.js under node.

Run: python3 tests/test_present_accept.py
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
node = shutil.which("node")
if not node:
    print("skipped: node isn't installed, so model/Present.js wasn't run")
    sys.exit(0)


def body(name):
    text = (root / "model" / name).read_text()
    return "\n".join(l for l in text.splitlines() if not l.startswith((".pragma", ".import")))


status = body("Status.js")
names = re.findall(r"^function ([A-Za-z0-9_]+)", status, re.M)
A, B, C = "a" * 16, "b" * 16, "c" * 16
NOW = 2000000000
AUDIT = {"installed": True, "ran": True, "at": NOW, "unparsed": 0, "packages": [
    {"name": "openssl", "severity": "High", "kinds": [], "fixed": "3.0.2", "cves": 1, "ack": A},
    {"name": "zlib", "severity": "Low", "kinds": [], "fixed": "", "cves": 1, "ack": B}]}
DEPS = {"osvScanner": True, "osv": {"at": NOW, "folder": "~", "scanned": 1, "failed": 0, "findings": [
    {"repo": "app", "file": "package-lock.json", "package": "lodash", "version": "1", "severity": "High",
     "count": 1, "vulns": [{"id": "GHSA-1", "fixed": ["2"]}], "fixable": True, "ack": A}]}}
LEAKS = {"gitleaks": True, "leaks": {"at": NOW, "folder": "~", "scanned": 1, "repos": 1, "failed": 0, "findings": [
    {"repo": "app", "file": "test.py", "line": 1, "rule": "generic-api-key", "commit": "abcd1234", "ack": A}]}}
OUTSIDE = {"hand": [{"name": "git", "where": "~/.local/bin", "shadows": True, "ack": A}], "notInAur": [],
           "notInAurAcks": []}
FAILED = {"units": [{"unit": "bluetooth.service", "user": False, "description": "Bluetooth", "ack": A}], "more": 0}

# name, call, accepted, kind wanted, words in the status, rows ticked
CASES = [
    ("audit, none accepted", "audit(%s, true, %d)" % (json.dumps(AUDIT), NOW), {}, "crit", "An update fixes 1", 0),
    ("audit, the fixable one accepted", "audit(%s, true, %d)" % (json.dumps(AUDIT), NOW), {"audit": [A]},
     "info", "none fixed yet", 1),
    ("audit, all accepted", "audit(%s, true, %d)" % (json.dumps(AUDIT), NOW), {"audit": [A, B]},
     "info", "left to review", 2),
    ("audit, accepted key of another finding", "audit(%s, true, %d)" % (json.dumps(AUDIT), NOW), {"audit": [C]},
     "crit", "An update fixes 1", 0),
    ("deps, none accepted", "deps(%s, %d)" % (json.dumps(DEPS), NOW), {}, "attn", "1 dependency has", 0),
    ("deps, accepted", "deps(%s, %d)" % (json.dumps(DEPS), NOW), {"deps": [A]}, "info", "left to review", 1),
    ("leaks, none accepted", "leaks(%s, %d)" % (json.dumps(LEAKS), NOW), {}, "attn", "1 possible secret", 0),
    ("leaks, accepted", "leaks(%s, %d)" % (json.dumps(LEAKS), NOW), {"leaks": [A]}, "info", "left to review", 1),
    ("outside, shadowing program", "outside(%s, {}, %d)" % (json.dumps(OUTSIDE), NOW), {}, "attn", "hides the packaged", 0),
    ("outside, accepted", "outside(%s, {}, %d)" % (json.dumps(OUTSIDE), NOW), {"outside": [A]},
     "info", "covers everything else", 1),
    ("failed, none accepted", "failed(%s)" % json.dumps(FAILED), {}, "info", "1 service has failed", 0),
    ("failed, accepted", "failed(%s)" % json.dumps(FAILED), {"failed": [A]}, "good", "expected failure", 1),
    # A key in another check's list doesn't count.
    ("deps key under leaks", "deps(%s, %d)" % (json.dumps(DEPS), NOW), {"leaks": [A]}, "attn", "1 dependency has", 0),
]
script = status + "\nvar Status = {%s};\n" % ",".join("%s: %s" % (n, n) for n in names) + body("Present.js") + "\nvar out = [];\n"
for name, call, accepted, *_ in CASES:
    script += ("ACC = %s; (function() { var r = %s; out.push([r.kind, r.status, (r.facts || [])"
               ".filter(function(f) { return f.ack && f.ack.on }).length, (r.facts || []).filter(function(f) { return f.ack }).length]) })();\n"
               % (json.dumps(accepted), call))
script += "console.log(JSON.stringify(out));\n"
proc = subprocess.run([node, "-"], input=script.encode(), capture_output=True, timeout=30)
if proc.returncode != 0:
    print(proc.stderr.decode())
    sys.exit(1)
bad = []
for (name, _, _, kind, words, ticked), (got_kind, got_status, got_ticked, boxes) in zip(CASES, json.loads(proc.stdout)):
    if got_kind != kind or words.lower() not in got_status.lower() or got_ticked != ticked or not boxes:
        bad.append("%s: %s %r, %d ticked of %d" % (name, got_kind, got_status, got_ticked, boxes))
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: %d states with accepted findings shown as they should be" % len(CASES))
