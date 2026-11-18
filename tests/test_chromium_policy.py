"""The Chromium privacy policy may only cut what the browser sends, never
switch off a protection, and must say so truthfully. A policy file from an
older Keepwell that turned off leaked-password warnings is found and an
update is offered.

Run: python3 tests/test_chromium_policy.py
"""

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "bin"))
check = runpy.run_path(str(root / "bin" / "keepwell-check"), run_name="keepwell_check")
run = runpy.run_path(str(root / "bin" / "keepwell-run"), run_name="keepwell_run")
policies = run["CHROMIUM_POLICIES"]
bad = []

if policies != check["CHROMIUM_POLICIES"]:
    bad.append("bin/keepwell-run and bin/keepwell-check have different policy lists")
# Policies that switch off a protection when set this way.
LOWERING = {"PasswordLeakDetectionEnabled": False, "SafeBrowsingEnabled": False,
            "SafeBrowsingProtectionLevel": 0, "ComponentUpdatesEnabled": False,
            "PasswordManagerEnabled": False, "SafeBrowsingProxiedRealTimeChecksAllowed": False,
            "DownloadRestrictions": 0, "SSLErrorOverrideAllowed": True}
for k, v in LOWERING.items():
    if k in policies and policies[k] == v:
        bad.append("the policy switches off a protection: %s = %r" % (k, v))
summary = run["ACTIONS"]["chromium-policy"]["summary"] if "ACTIONS" in run else ""
m = re.search(r"(\d+) settings", summary)
if not m or int(m.group(1)) != len(policies) or "none of which lowers security" not in summary:
    bad.append("the action's summary doesn't match the policy: %r" % summary)

# An older Keepwell's file on disk.
d = tempfile.mkdtemp(prefix="keepwell-policy-")
try:
    def probe(doc):
        with open(os.path.join(d, "keepwell-privacy.json"), "w") as f:
            json.dump(doc, f)
        return check["probe_chromium_policy"](d)
    r = probe(policies)
    if r["outdated"] or r["lowersSecurity"] or r["set"] != len(policies):
        bad.append("current policy: %r" % r)
    old = dict(policies, PasswordLeakDetectionEnabled=False)
    r = probe(old)
    if not (r["outdated"] and r["lowersSecurity"]):
        bad.append("1.2.12's policy not flagged: %r" % r)
    r = probe({k: v for k, v in list(policies.items())[:-1]})
    if not r["outdated"] or r["lowersSecurity"]:
        bad.append("an incomplete policy: %r" % r)
finally:
    shutil.rmtree(d, ignore_errors=True)

# What the check shows for the old file (Present.js under node).
node = shutil.which("node")
if node:
    def body(name):
        text = (root / "model" / name).read_text()
        return "\n".join(l for l in text.splitlines() if not l.startswith((".pragma", ".import")))
    status = body("Status.js")
    names = re.findall(r"^function ([A-Za-z0-9_]+)", status, re.M)
    script = status + "\nvar Status = {%s};\n" % ",".join("%s: %s" % (n, n) for n in names) + body("Present.js") + """
var r = browser({ chromium: true, profile: true }, { set: 12, total: 13, keepwell: true, outdated: true, lowersSecurity: true });
var ok = browser({ chromium: true, profile: true }, { set: 13, total: 13, keepwell: true, outdated: false });
console.log(JSON.stringify([r.kind, r.status, r.actions.map(function(a) { return a.act }), ok.kind, ok.status]));
"""
    proc = subprocess.run([node, "-"], input=script.encode(), capture_output=True, timeout=30)
    got = json.loads(proc.stdout) if proc.returncode == 0 else None
    if not got or got[0] != "attn" or "leaked-password" not in got[1] or got[2][0] != "chromium-policy" \
            or got[3] != "good" or got[4] != "Privacy policy is in force":
        bad.append("browser check: %r %s" % (got, proc.stderr.decode()[-500:]))
else:
    print("note: node isn't installed, so what the check shows wasn't run")

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: the privacy policy switches off no protection, says so, and an older one is caught")
