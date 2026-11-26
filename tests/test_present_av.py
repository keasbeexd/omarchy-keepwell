"""The Antivirus row names what a scan couldn't reach, so it can be dealt
with, and says how many files were deleted while it ran, without making a
complete scan look incomplete. Runs model/Present.js under node.

Run: python3 tests/test_present_av.py
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
NOW = 1795700000
SCAN = {"at": NOW - 3600, "target": "home", "finished": True, "files": 330000, "infected": 0,
        "complete": True, "found": [], "allowedFound": 0, "vanished": 0, "notScanned": [], "oddNames": []}
BASE = {"clamav": True, "definitionsAt": NOW - 3600, "freshclamEnabled": "enabled", "scanning": False,
        "allowed": 0}
CASES = [
    # name, lastScan changes, kind, words in status, facts that must be there, facts that must not
    ("clean", {}, "good", "up to date", [], ["Not scanned", "Deleted while scanning"]),
    ("vanished, complete", {"vanished": 41}, "good", "up to date", ["Deleted while scanning: 41 files"],
     ["Incomplete"]),
    ("one not scanned", {"complete": False, "incomplete": "1 file couldn't be scanned",
                         "notScanned": ["~/f: Not supported file type"]},
     "attn", "incomplete", ["Incomplete: 1 file couldn't be scanned", "Not scanned: ~/f: Not supported file type"], []),
    ("odd name", {"complete": False, "incomplete": "1 file with unusual names skipped",
                  "oddNames": ["~/line\\x0abreak.txt"]},
     "attn", "incomplete", ["Not scanned: ~/line\\x0abreak.txt"], []),
    ("unexplained error", {"complete": False, "incomplete": "ClamAV stopped with an error",
                           "clamSaid": "ERROR: Can't open file list"},
     "attn", "incomplete", ["ClamAV said: ERROR: Can't open file list"], []),
]
script = status + "\nvar Status = {%s};\n" % ",".join("%s: %s" % (n, n) for n in names) + body("Present.js") + """
var base = %s, scan = %s, cases = %s, out = [];
cases.forEach(function(c) {
  var r = antivirus(Object.assign({}, base, {lastScan: Object.assign({}, scan, c[1])}), %d);
  out.push([r.kind, r.status, (r.facts || []).map(function(f) { return f.k + ": " + f.v })]) });
console.log(JSON.stringify(out));
""" % (json.dumps(BASE), json.dumps(SCAN), json.dumps(CASES), NOW)
proc = subprocess.run([node, "-"], input=script.encode(), capture_output=True, timeout=30)
if proc.returncode != 0:
    print(proc.stderr.decode())
    sys.exit(1)
bad = []
for (name, _, kind, words, want, unwanted), (got_kind, got_status, facts) in zip(CASES, json.loads(proc.stdout)):
    if got_kind != kind or words not in got_status:
        bad.append("%s: %s %r" % (name, got_kind, got_status))
    for f in want:
        if f not in facts:
            bad.append("%s: missing %r in %r" % (name, f, facts))
    for f in unwanted:
        if any(x.startswith(f) for x in facts):
            bad.append("%s: unexpected %r in %r" % (name, f, facts))
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: %d Antivirus states shown as they should be" % len(CASES))
